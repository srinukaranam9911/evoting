from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_db, hash_password, get_constituencies
import os
from auth import admin_login_required, send_winner_email
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import flash  # Add this if not already imported

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
        # Activate elections
        db.execute("""
            UPDATE elections
            SET status = 'active'
            WHERE start_time <= ? AND end_time >= ? AND status = 'upcoming'
        """, (current_time, current_time))

        # Find newly completed elections
        completed = db.execute("""
            SELECT * FROM elections
            WHERE end_time < ? AND status != 'completed'
        """, (current_time,)).fetchall()

        # Mark completed + send winner emails
        for election in completed:
            db.execute("UPDATE elections SET status='completed' WHERE id=?", (election['id'],))
            send_election_winner_email(election['id'])

        db.commit()



# ----------------------------------------------------------------------
# SEND WINNER EMAIL
# ----------------------------------------------------------------------
def send_election_winner_email(election_id):
    with get_db() as db:
        election = db.execute('SELECT * FROM elections WHERE id = ?', (election_id,)).fetchone()
        if not election:
            return False

        results = db.execute("""
            SELECT c.name, c.party, COUNT(v.id) AS vote_count
            FROM candidates c
            LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = ?
            WHERE c.constituency = ?
            GROUP BY c.id
            ORDER BY vote_count DESC
        """, (election_id, election['constituency'])).fetchall()

        if not results:
            return False

        total_votes = sum(r['vote_count'] for r in results)
        winner = results[0]
        winner_percentage = (winner['vote_count'] / total_votes * 100) if total_votes else 0

        admins = db.execute("SELECT * FROM admins").fetchall()
        admin_emails = [a['username'] for a in admins]

        subject = f"Election Results: {election['title']}"

        text_content = f"""
WINNER: {winner['name']} ({winner['party']})
Votes: {winner['vote_count']} ({winner_percentage:.1f}%)
"""

        html_content = "<h2>Election Results</h2>"

        sent = False
        for email in admin_emails:
            if send_winner_email(email, subject, text_content, html_content):
                sent = True

        return sent



# ----------------------------------------------------------------------
# ADMIN LOGIN
# ----------------------------------------------------------------------
@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])

        with get_db() as db:
            admin = db.execute(
                "SELECT * FROM admins WHERE username=? AND password=?",
                (username, password)
            ).fetchone()

        if admin:
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash("Login successful!", "success")
            return redirect(url_for('admin_routes.admin_dashboard'))

        flash("Invalid credentials", "error")

    return render_template('admin_login.html')



# ----------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------
@admin_bp.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    update_election_status()

    with get_db() as db:
        total_voters = db.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
        total_candidates = db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        active_elections = db.execute("SELECT COUNT(*) FROM elections WHERE status='active'").fetchone()[0]
        total_votes = db.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        elections = db.execute("SELECT * FROM elections ORDER BY created_at DESC").fetchall()

    return render_template(
        'admin_dashboard.html',
        total_voters=total_voters,
        total_candidates=total_candidates,
        active_elections=active_elections,
        total_votes=total_votes,
        elections=elections
    )

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
            db.execute("""
                INSERT INTO elections (title, description, constituency, start_time, end_time, status)
                VALUES (?, ?, ?, ?, ?, ?)
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
        candidates = db.execute("SELECT * FROM candidates").fetchall()

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
        db.execute("""
            INSERT INTO candidates (name, party, constituency, photo_path, symbol_path)
            VALUES (?, ?, ?, ?, ?)
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
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()

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
            db.execute("""
                UPDATE candidates
                SET name=?, party=?, constituency=?, photo_path=?, symbol_path=?
                WHERE id=?
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
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()

        if not candidate:
            flash("Candidate not found!", "error")
            return redirect(url_for('admin_routes.manage_candidates'))

        # Remove files
        if candidate['photo_path'] and os.path.exists(os.path.join('static/uploads', candidate['photo_path'])):
            os.remove(os.path.join('static/uploads', candidate['photo_path']))

        if candidate['symbol_path'] and os.path.exists(os.path.join('static/uploads', candidate['symbol_path'])):
            os.remove(os.path.join('static/uploads', candidate['symbol_path']))

        db.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
        db.commit()

    flash("Candidate deleted!", "success")
    return redirect(url_for('admin_routes.manage_candidates'))


# ----------------------------------------------------------------------
# EDIT ELECTION  (FIX FOR BuildError)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/elections/<int:election_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_election(election_id):
    with get_db() as db:
        election = db.execute(
            "SELECT * FROM elections WHERE id = ?",
            (election_id,)
        ).fetchone()

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
            db.execute("""
                UPDATE elections
                SET title=?, description=?, constituency=?, start_time=?, end_time=?, status=?
                WHERE id=?
            """, (title, description, constituency, start_time, end_time, status, election_id))
            db.commit()

        flash("Election updated successfully!", "success")
        return redirect(url_for('admin_routes.admin_dashboard'))

    # Convert SQL datetime to datetime-local input format
    election_data = dict(election)
    election_data["start_time"] = election["start_time"].replace(" ", "T")
    election_data["end_time"] = election["end_time"].replace(" ", "T")

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
        election = db.execute("SELECT * FROM elections WHERE id=?", (election_id,)).fetchone()
        if not election:
            flash("Election not found!", "error")
            return redirect(url_for('admin_routes.admin_dashboard'))

        # Optional: delete related votes
        db.execute("DELETE FROM votes WHERE election_id=?", (election_id,))
        # Delete the election itself
        db.execute("DELETE FROM elections WHERE id=?", (election_id,))
        db.commit()

    flash("Election deleted successfully!", "success")
    return redirect(url_for('admin_routes.admin_dashboard'))


# ----------------------------------------------------------------------
# VIEW ELECTION RESULTS  (FIX FOR BuildError)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/results')
@admin_login_required
def view_results():
    election_id = request.args.get('election_id')

    with get_db() as db:
        elections = db.execute("SELECT * FROM elections").fetchall()

        if election_id:
            results = db.execute("""
                SELECT c.name, c.party, COUNT(v.id) AS vote_count
                FROM candidates c
                LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = ?
                WHERE c.constituency = (SELECT constituency FROM elections WHERE id = ?)
                GROUP BY c.id
                ORDER BY vote_count DESC
            """, (election_id, election_id)).fetchall()

            election = db.execute(
                "SELECT * FROM elections WHERE id=?",
                (election_id,)
            ).fetchone()
        else:
            results = []
            election = None

    return render_template(
        'election_results.html',
        elections=elections,
        results=results,
        election=election
    )

# ----------------------------------------------------------------------
# SEND WINNER EMAIL TO VOTERS (UPDATED)
# ----------------------------------------------------------------------
def send_election_winner_email(election_id):
    """
    Sends winner email to all registered voters.
    Returns (True, "sent") on success, (False, "reason") on failure.
    """
    try:
        with get_db() as db:
            election = db.execute('SELECT * FROM elections WHERE id = ?', (election_id,)).fetchone()
            if not election:
                return False, "election_not_found"

            # Get results for the election's constituency
            results = db.execute("""
                SELECT c.name, c.party, COUNT(v.id) AS vote_count
                FROM candidates c
                LEFT JOIN votes v ON c.id = v.candidate_id AND v.election_id = ?
                WHERE c.constituency = ?
                GROUP BY c.id
                ORDER BY vote_count DESC
            """, (election_id, election['constituency'])).fetchall()

            if not results:
                return False, "no_results"

            total_votes = sum(int(r['vote_count']) for r in results)
            winner = results[0]
            winner_percentage = (winner['vote_count'] / total_votes * 100) if total_votes else 0.0

            # Get all registered voters' emails
            voters = db.execute("SELECT email FROM voters WHERE email IS NOT NULL AND email != ''").fetchall()
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
# ADMIN LOGOUT  (REQUIRED BY base.html)
# ----------------------------------------------------------------------
@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash("Logged out successfully!", "success")
    return redirect(url_for('admin_routes.admin_login'))
