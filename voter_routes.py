from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db, hash_password, get_constituencies  # ADD get_constituencies here
import os
from auth import voter_login_required, generate_otp, send_otp_email, log_audit
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import get_constituencies
import sqlite3

voter_bp = Blueprint('voter_routes', __name__)

def get_current_voter():
    """Get current voter from session"""
    if 'voter_id' in session:
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute('SELECT * FROM voters WHERE id = %s', (session['voter_id'],))
                return cursor.fetchone()
    return None

def get_voter_history(voter_id):
    """Get voting history for a voter"""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    e.title as election_title,
                    e.constituency,
                    c.name as candidate_name,
                    c.party,
                    v.voted_at
                FROM votes v
                JOIN elections e ON v.election_id = e.id
                JOIN candidates c ON v.candidate_id = c.id
                WHERE v.voter_id = %s
                ORDER BY v.voted_at DESC
            ''', (voter_id,))
            return cursor.fetchall()

def update_election_status():
    """Update election status based on current time - same as in admin_routes"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as db:
        with db.cursor() as cursor:
            # Update to active
            cursor.execute('''
                UPDATE elections 
                SET status = 'active' 
                WHERE start_time <= %s AND end_time >= %s AND status = 'upcoming'
            ''', (current_time, current_time))
            
            # Update to completed
            cursor.execute('''
                UPDATE elections 
                SET status = 'completed' 
                WHERE end_time < %s AND status != 'completed'
            ''', (current_time,))
            db.commit()

@voter_bp.route('/voter/login', methods=['GET', 'POST'])
def voter_login():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM voters WHERE email = %s AND password = %s',
                    (email, password)
                )
                voter = cursor.fetchone()
            
            if voter:
                # Check if voter is verified
                if not voter['is_verified']:
                    flash('Please verify your email before logging in', 'error')
                    return redirect(url_for('voter_routes.verify_email'))
                
                session['voter_id'] = voter['id']
                session['voter_name'] = voter['name']
                session['voter_email'] = voter['email']
                session['voter_constituency'] = voter['constituency']
                flash('Login successful!', 'success')
                return redirect(url_for('voter_routes.voter_dashboard'))
            else:
                flash('Invalid credentials', 'error')
    
    return render_template('voter_login.html')

@voter_bp.route('/voter/register', methods=['GET', 'POST'])
def voter_register():
    # GET CONSTITUENCIES FROM DATABASE
    constituencies = get_constituencies()
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = hash_password(request.form['password'])
        constituency = request.form['constituency']
        # Aadhar number removed
        
        with get_db() as db:
            with db.cursor() as cursor:
                # Check if email already exists
                cursor.execute(
                    'SELECT * FROM voters WHERE email = %s', (email,)
                )
                existing_voter = cursor.fetchone()
            
            if existing_voter:
                flash('Email already registered', 'error')
                return render_template('voter_register.html', constituencies=constituencies)  # PASS CONSTITUENCIES ON ERROR
            
            # Generate OTP
            otp = generate_otp()
            otp_expiry = datetime.now().timestamp() + 600  # 10 minutes
            
            # Store voter data in session for verification
            session['pending_voter'] = {
                'name': name,
                'email': email,
                'password': password,
                'constituency': constituency,
                'otp': otp,
                'otp_expiry': otp_expiry
            }
            
            # Send OTP email
            if send_otp_email(email, otp):
                flash('OTP sent to your email. Please verify to complete registration.', 'success')
                return redirect(url_for('voter_routes.verify_email'))
            else:
                flash('Failed to send OTP. Please try again.', 'error')
    
    # PASS CONSTITUENCIES TO TEMPLATE FOR BOTH GET AND POST
    return render_template('voter_register.html', constituencies=constituencies)

@voter_bp.route('/voter/verify-email', methods=['GET', 'POST'])
def verify_email():
    # Check if pending voter data exists
    pending = session.get('pending_voter')
    if not pending:
        flash('Session expired. Please register again.', 'error')
        return redirect(url_for('voter_routes.voter_register'))

    # Handle POST - user submitted OTP
    if request.method == 'POST':
        entered_otp = request.form.get('otp', '')
        saved_otp = pending['otp']
        expiry_time = pending['otp_expiry']

        # Check expiry
        if datetime.now().timestamp() > expiry_time:
            session.pop('pending_voter', None)
            flash('OTP expired. Please register again.', 'error')
            return redirect(url_for('voter_routes.voter_register'))

        # Check OTP match
        if entered_otp != saved_otp:
            flash('Invalid verification code', 'error')
            return redirect(url_for('voter_routes.verify_email'))

        # OTP is correct → save voter to DB
        with get_db() as db:
            with db.cursor() as cursor:
                # Use 't' for true in PostgreSQL
                cursor.execute('''
                    INSERT INTO voters (name, email, password, constituency, is_verified)
                    VALUES (%s, %s, %s, %s, 't')
                ''', (pending['name'], pending['email'], pending['password'], pending['constituency']))
                db.commit()

        # Clear session pending data
        session.pop('pending_voter', None)
        flash('Email verified successfully! You can now log in.', 'success')

        return redirect(url_for('voter_routes.voter_login'))

    return render_template('verify_email.html')


@voter_bp.route('/voter/dashboard')
@voter_login_required
def voter_dashboard():
    update_election_status()  # Update election status first
    
    with get_db() as db:
        with db.cursor() as cursor:
            # Get active elections for voter's constituency
            cursor.execute('''
                SELECT * FROM elections 
                WHERE status = 'active' AND constituency = %s
                ORDER BY created_at DESC
            ''', (session['voter_constituency'],))
            active_elections = cursor.fetchall()
            
            # Get upcoming elections
            cursor.execute('''
                SELECT * FROM elections 
                WHERE status = 'upcoming' AND constituency = %s
                ORDER BY start_time ASC
            ''', (session['voter_constituency'],))
            upcoming_elections = cursor.fetchall()
            
            # Get elections the voter has already voted in
            cursor.execute('''
                SELECT e.* FROM elections e
                JOIN votes v ON e.id = v.election_id
                WHERE v.voter_id = %s
            ''', (session['voter_id'],))
            voted_elections = cursor.fetchall()
            
            # Get completed elections in voter's constituency
            cursor.execute('''
                SELECT * FROM elections 
                WHERE status = 'completed' AND constituency = %s
                ORDER BY end_time DESC
            ''', (session['voter_constituency'],))
            completed_elections = cursor.fetchall()
    
    # Convert datetime objects to string format
    def format_election_datetimes(elections_list):
        formatted = []
        for election in elections_list:
            election_data = dict(election)
            election_data['start_time'] = election['start_time'].strftime('%Y-%m-%d %H:%M')
            election_data['end_time'] = election['end_time'].strftime('%Y-%m-%d %H:%M')
            if election.get('created_at'):
                election_data['created_at'] = election['created_at'].strftime('%Y-%m-%d %H:%M')
            formatted.append(election_data)
        return formatted
    
    return render_template('voter_dashboard.html',
                         active_elections=format_election_datetimes(active_elections),
                         upcoming_elections=format_election_datetimes(upcoming_elections),
                         voted_elections=format_election_datetimes(voted_elections),
                         completed_elections=format_election_datetimes(completed_elections))

@voter_bp.route('/voter/vote/<int:election_id>')
@voter_login_required
def vote(election_id):
    with get_db() as db:
        with db.cursor() as cursor:
            # Check if election exists and is active
            cursor.execute(
                'SELECT * FROM elections WHERE id = %s AND status = \'active\'',
                (election_id,)
            )
            election = cursor.fetchone()
            
            if not election:
                flash('Election not found or not active', 'error')
                return redirect(url_for('voter_routes.voter_dashboard'))
            
            # Check if voter has already voted in this election
            cursor.execute(
                'SELECT * FROM votes WHERE voter_id = %s AND election_id = %s',
                (session['voter_id'], election_id)
            )
            existing_vote = cursor.fetchone()
            
            if existing_vote:
                flash('You have already voted in this election', 'error')
                return redirect(url_for('voter_routes.voter_dashboard'))
            
            # Check if voter's constituency matches election constituency
            if session['voter_constituency'] != election['constituency']:
                flash('This election is not for your constituency', 'error')
                return redirect(url_for('voter_routes.voter_dashboard'))
            
            # Get candidates for this election (same constituency)
            cursor.execute('''
                SELECT * FROM candidates 
                WHERE constituency = %s
                ORDER BY name
            ''', (election['constituency'],))
            candidates = cursor.fetchall()
    
    # Convert datetime objects to string format for template
    election_data = dict(election)
    election_data['start_time'] = election['start_time'].strftime('%Y-%m-%d %H:%M')
    election_data['end_time'] = election['end_time'].strftime('%Y-%m-%d %H:%M')
    
    return render_template('vote.html', 
                         election=election_data, 
                         candidates=candidates)

@voter_bp.route('/voter/submit-vote/<int:election_id>', methods=['POST'])
@voter_login_required
def submit_vote(election_id):
    candidate_id = request.form.get('candidate_id')
    
    if not candidate_id:
        flash('Please select a candidate', 'error')
        return redirect(url_for('voter_routes.vote', election_id=election_id))
    
    with get_db() as db:
        with db.cursor() as cursor:
            # Double-check voting constraints
            cursor.execute(
                'SELECT * FROM elections WHERE id = %s AND status = \'active\'',
                (election_id,)
            )
            election = cursor.fetchone()
            
            if not election:
                flash('Election not found or not active', 'error')
                return redirect(url_for('voter_routes.voter_dashboard'))
            
            cursor.execute(
                'SELECT * FROM votes WHERE voter_id = %s AND election_id = %s',
                (session['voter_id'], election_id)
            )
            existing_vote = cursor.fetchone()
            
            if existing_vote:
                flash('You have already voted in this election', 'error')
                return redirect(url_for('voter_routes.voter_dashboard'))
            
            # Verify candidate exists and is in correct constituency
            cursor.execute(
                'SELECT * FROM candidates WHERE id = %s AND constituency = %s',
                (candidate_id, election['constituency'])
            )
            candidate = cursor.fetchone()
            
            if not candidate:
                flash('Invalid candidate selection', 'error')
                return redirect(url_for('voter_routes.vote', election_id=election_id))
            
            # Record the vote
            try:
                # Try with voted_at first
                cursor.execute('''
                    INSERT INTO votes (voter_id, election_id, candidate_id, voted_at)
                    VALUES (%s, %s, %s, %s)
                ''', (session['voter_id'], election_id, candidate_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            except Exception as e:
                # If voted_at column doesn't exist or other error, insert without it
                cursor.execute('''
                    INSERT INTO votes (voter_id, election_id, candidate_id)
                    VALUES (%s, %s, %s)
                ''', (session['voter_id'], election_id, candidate_id))
            
            db.commit()
            
            # Log the voting action
            log_audit('vote_cast', 'voter', session['voter_id'], 
                     f'Voted in election {election_id} for candidate {candidate_id}')
    
    flash('Vote cast successfully! Thank you for voting.', 'success')
    return redirect(url_for('voter_routes.voter_dashboard'))

@voter_bp.route('/voter/results')
@voter_login_required
def view_results():
    election_id = request.args.get('election_id')
    
    with get_db() as db:
        with db.cursor() as cursor:
            # Get elections in voter's constituency
            cursor.execute('''
                SELECT * FROM elections 
                WHERE constituency = %s AND status = 'completed'
                ORDER BY end_time DESC
            ''', (session['voter_constituency'],))
            elections = cursor.fetchall()
            
            if election_id:
                cursor.execute('''
                    SELECT c.name, c.party, COUNT(v.id) as vote_count
                    FROM candidates c
                    LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = %s
                    WHERE c.constituency = %s
                    GROUP BY c.id
                    ORDER BY vote_count DESC
                ''', (election_id, session['voter_constituency']))
                results = cursor.fetchall()
                
                cursor.execute('SELECT * FROM elections WHERE id = %s', (election_id,))
                election = cursor.fetchone()
            else:
                results = []
                election = None
    
    # Convert datetime objects to string format for template
    def format_election(election_data):
        if election_data:
            election_dict = dict(election_data)
            election_dict['start_time'] = election_data['start_time'].strftime('%Y-%m-%d %H:%M')
            election_dict['end_time'] = election_data['end_time'].strftime('%Y-%m-%d %H:%M')
            if election_data.get('created_at'):
                election_dict['created_at'] = election_data['created_at'].strftime('%Y-%m-%d %H:%M')
            return election_dict
        return None
    
    # Convert all elections in the list
    formatted_elections = []
    for e in elections:
        formatted_elections.append(format_election(e))
    
    return render_template('voter_results.html', 
                         elections=formatted_elections, 
                         results=results, 
                         election=format_election(election))

# FIXED: Changed @app.route to @voter_bp.route
@voter_bp.route('/voter/profile')
@voter_login_required
def voter_profile():
    voter = get_current_voter()
    
    if not voter:
        flash('Please login to view profile', 'error')
        return redirect(url_for('voter_routes.voter_login'))
    
    # Fetch voting history from database
    history = get_voter_history(voter['id'])
    
    # Format the history properly
    formatted_history = []
    for record in history:
        formatted_record = {
            'title': record['election_title'],
            'constituency': record['constituency'],
            'candidate_name': record['candidate_name'],
            'party': record['party'],
            'voted_at': record['voted_at']
        }
        
        # Handle voted_at - if it's a datetime object, convert to string
        # If it's already a string, leave it as is
        if hasattr(formatted_record['voted_at'], 'strftime'):
            formatted_record['voted_at'] = formatted_record['voted_at'].strftime('%Y-%m-%d %H:%M:%S')
        elif formatted_record['voted_at'] is None:
            formatted_record['voted_at'] = None
        
        formatted_history.append(formatted_record)
    
    # Ensure voter dict has required fields for template
    voter_dict = dict(voter)
    voter_dict['name'] = voter['name']
    voter_dict['email'] = voter['email']
    voter_dict['constituency'] = voter['constituency']
    voter_dict['is_verified'] = voter['is_verified']
    voter_dict['created_at'] = voter.get('created_at')  # Handle if created_at doesn't exist
    
    return render_template('voter_profile.html',
                         voter=voter_dict,
                         voting_history=formatted_history)

@voter_bp.route('/voter/logout')
def voter_logout():
    session.pop('voter_id', None)
    session.pop('voter_name', None)
    session.pop('voter_email', None)
    session.pop('voter_constituency', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('voter_routes.voter_login'))
