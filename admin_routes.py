from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_db, hash_password, get_constituencies
import os
from auth import admin_login_required, send_winner_email
from datetime import datetime
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin_routes', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------------------------------------------------------------
# UPDATE ELECTION STATUS
# ----------------------------------------------------------------------
def update_election_status():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as db:
        with db.cursor() as cursor:
            # Activate elections
            cursor.execute("""
                UPDATE elections
                SET status = 'active'
                WHERE start_time <= %s AND end_time >= %s AND status = 'upcoming'
            """, (current_time, current_time))

            # Find newly completed elections
            cursor.execute("""
                SELECT * FROM elections
                WHERE end_time < %s AND status != 'completed'
            """, (current_time,))
            completed = cursor.fetchall()

            # Mark completed + send winner emails
            for election in completed:
                cursor.execute("UPDATE elections SET status='completed' WHERE id=%s", (election['id'],))
                send_election_winner_email(election['id'])

            db.commit()



# ----------------------------------------------------------------------
# SEND WINNER EMAIL
# ----------------------------------------------------------------------
def send_election_winner_email(election_id):
    """
    Sends winner email to all registered voters.
    Returns (True, "sent") on success, (False, "reason") on failure.
    """
    try:
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute('SELECT * FROM elections WHERE id = %s', (election_id,))
                election = cursor.fetchone()
                if not election:
                    return False, "election_not_found"

                # Get results for the election's constituency
                cursor.execute("""
                    SELECT c.name, c.party, COUNT(v.id) AS vote_count
                    FROM candidates c
                    LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = %s
                    WHERE c.constituency = %s
                    GROUP BY c.id
                    ORDER BY vote_count DESC
                """, (election_id, election['constituency']))
                results = cursor.fetchall()

                if not results:
                    return False, "no_results"

                total_votes = sum(int(r['vote_count']) for r in results)
                winner = results[0]
                winner_percentage = (winner['vote_count'] / total_votes * 100) if total_votes else 0.0

                # Get all registered voters' emails
                cursor.execute("SELECT email FROM voters WHERE email IS NOT NULL AND email != ''")
                voters = cursor.fetchall()
                voter_emails = [v['email'] for v in voters]

                if not voter_emails:
                    return False, "no_voter_emails_configured"

                subject = f"Election Results: {election['title']}"
                
                # Create more detailed content for voters
                text_content = f"""
ELECTION RESULTS: {election['title']}

CONSTITUENCY: {election['constituency']}

WINNER: {winner['name']} ({winner['party']})
Votes: {winner['vote_count']} ({winner_percentage:.1f}%)

FULL RESULTS:
"""
                html_content = f"""
<h2>Election Results: {election['title']}</h2>
<p><strong>Constituency:</strong> {election['constituency']}</p>

<div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0;">
    <h3 style="color: #856404; margin-top: 0;">🏆 WINNER</h3>
    <p style="font-size: 18px; font-weight: bold; color: #e67700;">
        {winner['name']} ({winner['party']})
    </p>
    <p>Votes: {winner['vote_count']} ({winner_percentage:.1f}%)</p>
</div>

<h3>Complete Results:</h3>
<table style="width: 100%; border-collapse: collapse;">
    <thead>
        <tr style="background: #f8f9fa;">
            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Candidate</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Party</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Votes</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Percentage</th>
        </tr>
    </thead>
    <tbody>
"""

                # Add all candidates to the email content
                for i, result in enumerate(results):
                    percentage = (result['vote_count'] / total_votes * 100) if total_votes else 0.0
                    text_content += f"{i+1}. {result['name']} ({result['party']}) - {result['vote_count']} votes ({percentage:.1f}%)\n"
                    
                    row_style = "background: #fff3cd;" if i == 0 else ""
                    html_content += f"""
        <tr style="{row_style}">
            <td style="padding: 10px; border: 1px solid #ddd;">{result['name']}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{result['party']}</td>
            <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{result['vote_count']}</td>
            <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{percentage:.1f}%</td>
        </tr>
"""

                # Close HTML content
                html_content += f"""
    </tbody>
    <tfoot>
        <tr style="background: #f8f9fa; font-weight: bold;">
            <td colspan="2" style="padding: 10px; border: 1px solid #ddd;">Total Votes</td>
            <td colspan="2" style="padding: 10px; border: 1px solid #ddd; text-align: right;">{total_votes}</td>
        </tr>
    </tfoot>
</table>

<p style="margin-top: 20px; color: #666; font-size: 12px;">
    This email was automatically sent by VoteSecure System.
</p>
"""

                sent_any = False
                # Try sending to each voter email
                for email in voter_emails:
                    try:
                        ok = send_winner_email(email, subject, text_content, html_content)
                        if ok:
                            sent_any = True
                    except Exception as ex:
                        print(f"[send_election_winner_email] failed sending to {email}: {ex}")

                if sent_any:
                    return True, f"sent_to_{len(voter_emails)}_voters"
                else:
                    return False, "send_failed"

    except Exception as e:
        print(f"[send_election_winner_email] unexpected error: {e}")
        return False, "error"



# ----------------------------------------------------------------------
# ADMIN LOGIN (FIXED VERSION)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        print(f"DEBUG: Login attempt for username: '{username}'")
        
        # Hash the entered password
        hashed_password = hash_password(password)
        print(f"DEBUG: Hashed password (first 20 chars): {hashed_password[:20]}...")
        
        with get_db() as db:
            with db.cursor() as cursor:
                # Check if any admin exists in the database
                cursor.execute("SELECT COUNT(*) as count FROM admins")
                admin_count = cursor.fetchone()['count']
                
                if admin_count == 0:
                    flash("No admin account exists. Please contact system administrator.", "error")
                    return redirect(url_for('admin_routes.admin_login'))
                
                # Direct lookup - exact username match
                cursor.execute(
                    "SELECT * FROM admins WHERE username = %s",
                    (username,)
                )
                admin = cursor.fetchone()
                
                if admin:
                    print(f"DEBUG: Found admin in DB: '{admin['username']}'")
                    print(f"DEBUG: DB password hash (first 20 chars): {admin['password'][:20]}...")
                    print(f"DEBUG: Entered password hash (first 20 chars): {hashed_password[:20]}...")
                    
                    # Compare password hashes
                    if admin['password'] == hashed_password:
                        session['admin_id'] = admin['id']
                        session['admin_username'] = admin['username']
                        flash("Login successful!", "success")
                        return redirect(url_for('admin_routes.admin_dashboard'))
                    else:
                        print("DEBUG: Password does not match")
                else:
                    print("DEBUG: No admin found with that username")

        flash("Invalid username or password", "error")

    return render_template('admin_login.html')


# ----------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------
@admin_bp.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    update_election_status()

    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM voters")
            total_voters = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) FROM candidates")
            total_candidates = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) FROM elections WHERE status='active'")
            active_elections = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) FROM votes")
            total_votes = cursor.fetchone()['count']
            
            cursor.execute("SELECT * FROM elections ORDER BY created_at DESC")
            elections = cursor.fetchall()
    
    # Convert datetime objects to string format
    def format_election(election_data):
        election_dict = dict(election_data)
        election_dict['start_time'] = election_data['start_time'].strftime('%Y-%m-%d %H:%M')
        election_dict['end_time'] = election_data['end_time'].strftime('%Y-%m-%d %H:%M')
        if election_data.get('created_at'):
            election_dict['created_at'] = election_data['created_at'].strftime('%Y-%m-%d %H:%M')
        return election_dict
    
    formatted_elections = [format_election(e) for e in elections]

    return render_template(
        'admin_dashboard.html',
        total_voters=total_voters,
        total_candidates=total_candidates,
        active_elections=active_elections,
        total_votes=total_votes,
        elections=formatted_elections
    )


# ----------------------------------------------------------------------
# CREATE ELECTION
# ----------------------------------------------------------------------
@admin_bp.route('/admin/elections/create', methods=['GET', 'POST'])
@admin_login_required
def create_election():
    constituencies = get_constituencies()

    if request.method == 'POST':
        title = request.form['title']
        constituency = request.form['constituency']
        start_time_raw = request.form['start_time']
        end_time_raw = request.form['end_time']
        description = request.form.get('description', '')

        # Convert HTML datetime-local to SQL datetime
        try:
            start_dt = datetime.strptime(start_time_raw, '%Y-%m-%dT%H:%M')
            end_dt = datetime.strptime(end_time_raw, '%Y-%m-%dT%H:%M')

            start_time = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_time = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            flash("Invalid date format!", "error")
            return redirect(url_for('admin_routes.create_election'))

        # Determine status
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if start_time > now:
            status = "upcoming"
        elif start_time <= now <= end_time:
            status = "active"
        else:
            status = "completed"

        # Insert election
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO elections (title, description, constituency, start_time, end_time, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (title, description, constituency, start_time, end_time, status))
                db.commit()

        flash("Election created successfully!", "success")
        return redirect(url_for('admin_routes.admin_dashboard'))

    # GET Request → Show form
    return render_template(
        "create_election.html",
        constituencies=constituencies
    )


# ----------------------------------------------------------------------
# MANAGE CANDIDATES (GET)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/candidates')
@admin_login_required
def manage_candidates():
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM candidates")
            candidates = cursor.fetchall()

    constituencies = get_constituencies()

    return render_template(
        'manage_candidates.html',
        candidates=candidates,
        constituencies=constituencies
    )


# ----------------------------------------------------------------------
# ADD CANDIDATE
# ----------------------------------------------------------------------
@admin_bp.route('/admin/candidates/add', methods=['POST'])
@admin_login_required
def add_candidate():
    name = request.form['name']
    party = request.form['party']
    constituency = request.form['constituency']

    # Handle photos
    photo = request.files.get('photo')
    symbol = request.files.get('symbol')

    photo_path = None
    symbol_path = None

    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)
        photo_path = f"photo_{datetime.now().timestamp()}_{filename}"
        photo.save(os.path.join('static/uploads', photo_path))

    if symbol and allowed_file(symbol.filename):
        filename = secure_filename(symbol.filename)
        symbol_path = f"symbol_{datetime.now().timestamp()}_{filename}"
        symbol.save(os.path.join('static/uploads', symbol_path))

    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO candidates (name, party, constituency, photo_path, symbol_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, party, constituency, photo_path, symbol_path))
            db.commit()

    flash("Candidate added!", "success")
    return redirect(url_for('admin_routes.manage_candidates'))


# ----------------------------------------------------------------------
# EDIT CANDIDATE
# ----------------------------------------------------------------------
@admin_bp.route('/admin/candidates/<int:candidate_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_candidate(candidate_id):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
            candidate = cursor.fetchone()

    if not candidate:
        flash("Candidate not found", "error")
        return redirect(url_for('admin_routes.manage_candidates'))

    constituencies = get_constituencies()

    if request.method == 'POST':
        name = request.form['name']
        party = request.form['party']
        constituency = request.form['constituency']

        photo_path = candidate['photo_path']
        symbol_path = candidate['symbol_path']

        # Photo
        photo = request.files.get('photo')
        if photo and allowed_file(photo.filename):
            if photo_path and os.path.exists(os.path.join('static/uploads', photo_path)):
                os.remove(os.path.join('static/uploads', photo_path))
            filename = secure_filename(photo.filename)
            photo_path = f"photo_{datetime.now().timestamp()}_{filename}"
            photo.save(os.path.join('static/uploads', photo_path))

        # Symbol
        symbol = request.files.get('symbol')
        if symbol and allowed_file(symbol.filename):
            if symbol_path and os.path.exists(os.path.join('static/uploads', symbol_path)):
                os.remove(os.path.join('static/uploads', symbol_path))
            filename = secure_filename(symbol.filename)
            symbol_path = f"symbol_{datetime.now().timestamp()}_{filename}"
            symbol.save(os.path.join('static/uploads', symbol_path))

        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute("""
                    UPDATE candidates
                    SET name=%s, party=%s, constituency=%s, photo_path=%s, symbol_path=%s
                    WHERE id=%s
                """, (name, party, constituency, photo_path, symbol_path, candidate_id))
                db.commit()

        flash("Candidate updated!", "success")
        return redirect(url_for('admin_routes.manage_candidates'))

    return render_template('edit_candidate.html', candidate=candidate, constituencies=constituencies)


# ----------------------------------------------------------------------
# DELETE CANDIDATE
# ----------------------------------------------------------------------
@admin_bp.route('/admin/candidates/<int:candidate_id>/delete', methods=['POST'])
@admin_login_required
def delete_candidate(candidate_id):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
            candidate = cursor.fetchone()

            if not candidate:
                flash("Candidate not found!", "error")
                return redirect(url_for('admin_routes.manage_candidates'))

            # Remove files
            if candidate['photo_path'] and os.path.exists(os.path.join('static/uploads', candidate['photo_path'])):
                os.remove(os.path.join('static/uploads', candidate['photo_path']))

            if candidate['symbol_path'] and os.path.exists(os.path.join('static/uploads', candidate['symbol_path'])):
                os.remove(os.path.join('static/uploads', candidate['symbol_path']))

            cursor.execute("DELETE FROM candidates WHERE id=%s", (candidate_id,))
            db.commit()

    flash("Candidate deleted!", "success")
    return redirect(url_for('admin_routes.manage_candidates'))


# ----------------------------------------------------------------------
# EDIT ELECTION
# ----------------------------------------------------------------------
@admin_bp.route('/admin/elections/<int:election_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_election(election_id):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM elections WHERE id = %s",
                (election_id,)
            )
            election = cursor.fetchone()

    if not election:
        flash("Election not found!", "error")
        return redirect(url_for('admin_routes.admin_dashboard'))

    constituencies = get_constituencies()

    if request.method == "POST":
        title = request.form["title"]
        constituency = request.form["constituency"]
        description = request.form.get("description", "")
        start_time_raw = request.form["start_time"]
        end_time_raw = request.form["end_time"]

        try:
            start_dt = datetime.strptime(start_time_raw, '%Y-%m-%dT%H:%M')
            end_dt = datetime.strptime(end_time_raw, '%Y-%m-%dT%H:%M')

            start_time = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_time = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            flash("Invalid date format!", "error")
            return redirect(url_for('admin_routes.edit_election', election_id=election_id))

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if start_time > now:
            status = "upcoming"
        elif start_time <= now <= end_time:
            status = "active"
        else:
            status = "completed"

        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute("""
                    UPDATE elections
                    SET title=%s, description=%s, constituency=%s, start_time=%s, end_time=%s, status=%s
                    WHERE id=%s
                """, (title, description, constituency, start_time, end_time, status, election_id))
                db.commit()

        flash("Election updated successfully!", "success")
        return redirect(url_for('admin_routes.admin_dashboard'))

    # Convert SQL datetime to datetime-local input format
    election_data = dict(election)
    election_data["start_time"] = election["start_time"].strftime('%Y-%m-%dT%H:%M')
    election_data["end_time"] = election["end_time"].strftime('%Y-%m-%dT%H:%M')

    return render_template(
        "edit_election.html",
        election=election_data,
        constituencies=constituencies
    )


# ----------------------------------------------------------------------
# DELETE ELECTION
# ----------------------------------------------------------------------
@admin_bp.route('/admin/elections/<int:election_id>/delete', methods=['POST'])
@admin_login_required
def delete_election(election_id):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM elections WHERE id=%s", (election_id,))
            election = cursor.fetchone()
            if not election:
                flash("Election not found!", "error")
                return redirect(url_for('admin_routes.admin_dashboard'))

            # Optional: delete related votes
            cursor.execute("DELETE FROM votes WHERE election_id=%s", (election_id,))
            # Delete the election itself
            cursor.execute("DELETE FROM elections WHERE id=%s", (election_id,))
            db.commit()

    flash("Election deleted successfully!", "success")
    return redirect(url_for('admin_routes.admin_dashboard'))


# ----------------------------------------------------------------------
# VIEW ELECTION RESULTS
# ----------------------------------------------------------------------
@admin_bp.route('/admin/results')
@admin_login_required
def view_results():
    election_id = request.args.get('election_id')

    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM elections ORDER BY created_at DESC")
            elections = cursor.fetchall()

            if election_id:
                cursor.execute("""
                    SELECT c.name, c.party, COUNT(v.id) AS vote_count
                    FROM candidates c
                    LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = %s
                    WHERE c.constituency = (SELECT constituency FROM elections WHERE id = %s)
                    GROUP BY c.id
                    ORDER BY vote_count DESC
                """, (election_id, election_id))
                results = cursor.fetchall()

                cursor.execute(
                    "SELECT * FROM elections WHERE id=%s",
                    (election_id,)
                )
                election = cursor.fetchone()
            else:
                results = []
                election = None
    
    # Convert datetime objects to string format
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

    return render_template(
        'election_results.html',
        elections=formatted_elections,
        results=results,
        election=format_election(election)
    )

# ----------------------------------------------------------------------
# MANUALLY SEND WINNER EMAIL TO VOTERS (UPDATED)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/send_winner_email_manual/<int:election_id>')
@admin_login_required
def send_winner_email_manual(election_id):
    """Manually trigger winner email for completed election to all voters"""
    success, reason = send_election_winner_email(election_id)
    
    if success:
        if "sent_to_" in reason:
            voter_count = reason.split("_")[2]  # Extract number from "sent_to_X_voters"
            flash(f"Winner email sent successfully to {voter_count} registered voters!", "success")
        else:
            flash("Winner email sent successfully to all registered voters!", "success")
    else:
        error_messages = {
            "election_not_found": "Election not found.",
            "no_results": "No voting results available for this election.",
            "no_voter_emails_configured": "No voter email addresses found in the system.",
            "send_failed": "Failed to send email. Please check email configuration.",
            "error": "An error occurred while sending emails."
        }
        flash(f"Failed to send winner email: {error_messages.get(reason, reason)}", "error")
    
    return redirect(url_for('admin_routes.view_results', election_id=election_id))

# ----------------------------------------------------------------------
# ADMIN LOGOUT
# ----------------------------------------------------------------------
@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash("Logged out successfully!", "success")
    return redirect(url_for('admin_routes.admin_login'))

