from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import hashlib
import os

db = SQLAlchemy()

class Voter(UserMixin, db.Model):
    __tablename__ = 'voters'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    constituency = db.Column(db.String(100), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with votes
    votes = db.relationship('Vote', backref='voter', lazy=True)
    
    def __repr__(self):
        return f'<Voter {self.name} ({self.email})>'
    
    def set_password(self, password):
        """Hash and set password"""
        self.password = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """Check password against hash"""
        return self.password == hashlib.sha256(password.encode()).hexdigest()
    
    def generate_otp(self):
        """Generate a 6-digit OTP"""
        import random
        import string
        self.otp = ''.join(random.choices(string.digits, k=6))
        self.otp_expiry = datetime.utcnow().replace(minute=datetime.utcnow().minute + 10)  # 10 minutes expiry
        return self.otp
    
    def verify_otp(self, otp):
        """Verify OTP"""
        if self.otp == otp and self.otp_expiry > datetime.utcnow():
            self.is_verified = True
            self.otp = None
            self.otp_expiry = None
            return True
        return False

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Admin {self.username}>'
    
    def set_password(self, password):
        """Hash and set password"""
        self.password = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """Check password against hash"""
        return self.password == hashlib.sha256(password.encode()).hexdigest()

class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    party = db.Column(db.String(100), nullable=False)
    constituency = db.Column(db.String(100), nullable=False)
    photo = db.Column(db.LargeBinary)  # Storing image as binary data
    symbol = db.Column(db.LargeBinary)  # Storing symbol as binary data
    photo_path = db.Column(db.String(255))  # Path to stored photo file
    symbol_path = db.Column(db.String(255))  # Path to stored symbol file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with votes
    votes = db.relationship('Vote', backref='candidate', lazy=True)
    
    def __repr__(self):
        return f'<Candidate {self.name} ({self.party})>'
    
    def get_photo_url(self):
        """Get URL for candidate photo"""
        if self.photo_path:
            return f'/static/uploads/{self.photo_path}'
        return 'https://via.placeholder.com/100/4361ee/ffffff?text=?'
    
    def get_symbol_url(self):
        """Get URL for party symbol"""
        if self.symbol_path:
            return f'/static/uploads/{self.symbol_path}'
        return 'https://via.placeholder.com/50/6c757d/ffffff?text=?'

class Election(db.Model):
    __tablename__ = 'elections'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    constituency = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='upcoming')  # upcoming, active, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with votes
    votes = db.relationship('Vote', backref='election', lazy=True)
    
    def __repr__(self):
        return f'<Election {self.title}>'
    
    def update_status(self):
        """Update election status based on current time"""
        now = datetime.utcnow()
        if now < self.start_time:
            self.status = 'upcoming'
        elif self.start_time <= now <= self.end_time:
            self.status = 'active'
        else:
            self.status = 'completed'
        return self.status
    
    def is_active(self):
        """Check if election is currently active"""
        now = datetime.utcnow()
        return self.start_time <= now <= self.end_time
    
    def has_ended(self):
        """Check if election has ended"""
        return datetime.utcnow() > self.end_time
    
    def get_candidates(self):
        """Get all candidates for this election's constituency"""
        return Candidate.query.filter_by(constituency=self.constituency).all()
    
    def get_results(self):
        """Get election results with vote counts"""
        from sqlalchemy import func
        return db.session.query(
            Candidate.id,
            Candidate.name,
            Candidate.party,
            Candidate.photo_path,
            Candidate.symbol_path,
            func.count(Vote.id).label('vote_count')
        ).outerjoin(Vote, (Candidate.id == Vote.candidate_id) & (Vote.election_id == self.id))\
         .filter(Candidate.constituency == self.constituency)\
         .group_by(Candidate.id)\
         .order_by(func.count(Vote.id).desc())\
         .all()

class Vote(db.Model):
    __tablename__ = 'votes'
    
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('voters.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent multiple votes per election
    __table_args__ = (db.UniqueConstraint('voter_id', 'election_id', name='unique_vote_per_election'),)
    
    def __repr__(self):
        return f'<Vote voter:{self.voter_id} candidate:{self.candidate_id} election:{self.election_id}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'voter' or 'admin'
    user_id = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_type}:{self.user_id}>'

class AIFraudDetection(db.Model):
    __tablename__ = 'ai_fraud_detection'
    
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('voters.id'))
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'))
    risk_score = db.Column(db.Float, default=0.0)  # 0.0 to 1.0
    detection_type = db.Column(db.String(50))  # 'multiple_voting_attempt', 'suspicious_location', etc.
    confidence = db.Column(db.Float, default=0.0)
    details = db.Column(db.Text)
    is_fraud = db.Column(db.Boolean, default=False)
    action_taken = db.Column(db.String(100))  # 'blocked', 'flagged', 'allowed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AIFraudDetection voter:{self.voter_id} score:{self.risk_score}>'

# Initialize database with sample data
def init_db(app):
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(
                username='admin',
                email='admin@votesecure.com'
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # Create sample candidates if none exist
        if Candidate.query.count() == 0:
            candidates = [
                Candidate(
                    name='John Anderson',
                    party='Progressive Students',
                    constituency='North Campus',
                    photo_path='default_candidate.jpg'
                ),
                Candidate(
                    name='Sarah Johnson',
                    party='United Students',
                    constituency='North Campus',
                    photo_path='default_candidate2.jpg'
                ),
                Candidate(
                    name='Michael Chen',
                    party='Science Alliance',
                    constituency='Science Department',
                    photo_path='default_candidate3.jpg'
                ),
                Candidate(
                    name='Emily Davis',
                    party='Arts Collective',
                    constituency='Arts Department',
                    photo_path='default_candidate4.jpg'
                )
            ]
            db.session.add_all(candidates)
        
        # Create sample election if none exist
        if Election.query.count() == 0:
            from datetime import datetime, timedelta
            election = Election(
                title='Student Union Election 2023',
                constituency='North Campus',
                start_time=datetime.utcnow() - timedelta(days=30),
                end_time=datetime.utcnow() - timedelta(days=15),
                status='completed'
            )
            db.session.add(election)
        
        db.session.commit()