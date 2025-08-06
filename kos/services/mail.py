"""
Mail system for KOS
"""

import time
import re
import smtplib
import imaplib
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

@dataclass
class EmailAddress:
    """Email address"""
    address: str
    name: Optional[str] = None
    
    def __str__(self):
        if self.name:
            return f'"{self.name}" <{self.address}>'
        return self.address
    
    @classmethod
    def parse(cls, email_str: str) -> 'EmailAddress':
        """Parse email string"""
        match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', email_str.strip())
        if match:
            return cls(address=match.group(2), name=match.group(1).strip())
        return cls(address=email_str.strip())

@dataclass
class Email:
    """Email message"""
    from_addr: EmailAddress
    to_addrs: List[EmailAddress]
    subject: str
    body: str
    cc_addrs: List[EmailAddress] = field(default_factory=list)
    bcc_addrs: List[EmailAddress] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    def to_mime(self) -> MIMEMultipart:
        """Convert to MIME message"""
        msg = MIMEMultipart()
        
        # Headers
        msg['From'] = str(self.from_addr)
        msg['To'] = ', '.join(str(addr) for addr in self.to_addrs)
        msg['Subject'] = self.subject
        msg['Date'] = time.strftime('%a, %d %b %Y %H:%M:%S %z', time.localtime(self.timestamp))
        
        if self.cc_addrs:
            msg['Cc'] = ', '.join(str(addr) for addr in self.cc_addrs)
        
        if self.message_id:
            msg['Message-ID'] = self.message_id
        
        if self.in_reply_to:
            msg['In-Reply-To'] = self.in_reply_to
        
        # Custom headers
        for key, value in self.headers.items():
            msg[key] = value
        
        # Body
        msg.attach(MIMEText(self.body, 'plain'))
        
        # Attachments
        for attachment in self.attachments:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment['data'])
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 
                          f'attachment; filename="{attachment["filename"]}"')
            msg.attach(part)
        
        return msg

class MailServer:
    """Mail server (simulated)"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.mailboxes: Dict[str, List[Email]] = {}
        self.users: Dict[str, Dict] = {}
        self.mail_dir = "/var/mail"
        self.config = {
            'domain': 'kos.local',
            'smtp_port': 25,
            'imap_port': 143,
            'pop3_port': 110,
            'max_message_size': 10485760  # 10MB
        }
        
        self._init_mail_system()
    
    def _init_mail_system(self):
        """Initialize mail system"""
        if not self.vfs:
            return
        
        # Create mail directory
        if not self.vfs.exists(self.mail_dir):
            try:
                self.vfs.mkdir(self.mail_dir)
            except:
                pass
        
        # Create default users
        self.add_user("root", "root@kos.local", "password")
        self.add_user("admin", "admin@kos.local", "admin123")
    
    def add_user(self, username: str, email: str, password: str) -> bool:
        """Add mail user"""
        if username in self.users:
            return False
        
        self.users[username] = {
            'email': email,
            'password': password,
            'quota': 104857600,  # 100MB
            'used': 0
        }
        
        self.mailboxes[email] = []
        
        # Create user mailbox directory
        if self.vfs:
            user_dir = f"{self.mail_dir}/{username}"
            if not self.vfs.exists(user_dir):
                try:
                    self.vfs.mkdir(user_dir)
                    self.vfs.mkdir(f"{user_dir}/inbox")
                    self.vfs.mkdir(f"{user_dir}/sent")
                    self.vfs.mkdir(f"{user_dir}/drafts")
                    self.vfs.mkdir(f"{user_dir}/trash")
                except:
                    pass
        
        return True
    
    def send_mail(self, email: Email) -> bool:
        """Send email (simulated)"""
        # Check sender
        sender = str(email.from_addr.address)
        if not self._is_local_address(sender):
            return False
        
        # Check size
        size = len(email.body)
        for attachment in email.attachments:
            size += len(attachment['data'])
        
        if size > self.config['max_message_size']:
            return False
        
        # Generate message ID
        if not email.message_id:
            email.message_id = f"<{time.time()}.{id(email)}@{self.config['domain']}>"
        
        # Deliver to recipients
        all_recipients = email.to_addrs + email.cc_addrs + email.bcc_addrs
        
        for recipient in all_recipients:
            addr = recipient.address
            
            if self._is_local_address(addr):
                # Local delivery
                if addr in self.mailboxes:
                    self.mailboxes[addr].append(email)
                    self._save_email(addr, email)
            else:
                # Would send to external server
                pass
        
        # Save to sender's sent folder
        self._save_to_sent(sender, email)
        
        return True
    
    def _is_local_address(self, address: str) -> bool:
        """Check if address is local"""
        return address.endswith(f"@{self.config['domain']}")
    
    def _save_email(self, address: str, email: Email):
        """Save email to user's mailbox"""
        if not self.vfs:
            return
        
        # Find username from email
        username = None
        for user, info in self.users.items():
            if info['email'] == address:
                username = user
                break
        
        if not username:
            return
        
        # Save to inbox
        inbox_dir = f"{self.mail_dir}/{username}/inbox"
        email_file = f"{inbox_dir}/{email.message_id.replace('<', '').replace('>', '')}.eml"
        
        try:
            with self.vfs.open(email_file, 'w') as f:
                f.write(str(email.to_mime()).encode())
        except:
            pass
    
    def _save_to_sent(self, address: str, email: Email):
        """Save email to sent folder"""
        if not self.vfs:
            return
        
        # Find username
        username = None
        for user, info in self.users.items():
            if info['email'] == address:
                username = user
                break
        
        if not username:
            return
        
        # Save to sent
        sent_dir = f"{self.mail_dir}/{username}/sent"
        email_file = f"{sent_dir}/{email.message_id.replace('<', '').replace('>', '')}.eml"
        
        try:
            with self.vfs.open(email_file, 'w') as f:
                f.write(str(email.to_mime()).encode())
        except:
            pass
    
    def get_inbox(self, email_address: str) -> List[Email]:
        """Get inbox emails"""
        return self.mailboxes.get(email_address, [])
    
    def delete_email(self, email_address: str, message_id: str) -> bool:
        """Delete email"""
        if email_address not in self.mailboxes:
            return False
        
        self.mailboxes[email_address] = [
            e for e in self.mailboxes[email_address]
            if e.message_id != message_id
        ]
        
        return True
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user"""
        if username not in self.users:
            return False
        
        return self.users[username]['password'] == password

class SMTPClient:
    """SMTP client for sending emails"""
    
    def __init__(self, server: str, port: int = 587, use_tls: bool = True):
        self.server = server
        self.port = port
        self.use_tls = use_tls
        self.username = None
        self.password = None
    
    def login(self, username: str, password: str):
        """Set login credentials"""
        self.username = username
        self.password = password
    
    def send(self, email: Email) -> bool:
        """Send email via SMTP"""
        try:
            # Connect to server
            if self.use_tls:
                server = smtplib.SMTP(self.server, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.server, self.port)
            
            # Login if credentials provided
            if self.username and self.password:
                server.login(self.username, self.password)
            
            # Send email
            msg = email.to_mime()
            all_recipients = [addr.address for addr in 
                            email.to_addrs + email.cc_addrs + email.bcc_addrs]
            
            server.send_message(msg, email.from_addr.address, all_recipients)
            server.quit()
            
            return True
        except Exception as e:
            print(f"SMTP Error: {e}")
            return False

class IMAPClient:
    """IMAP client for receiving emails"""
    
    def __init__(self, server: str, port: int = 993, use_ssl: bool = True):
        self.server = server
        self.port = port
        self.use_ssl = use_ssl
        self.connection = None
    
    def connect(self, username: str, password: str) -> bool:
        """Connect to IMAP server"""
        try:
            if self.use_ssl:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.connection = imaplib.IMAP4(self.server, self.port)
            
            self.connection.login(username, password)
            return True
        except Exception as e:
            print(f"IMAP Error: {e}")
            return False
    
    def list_folders(self) -> List[str]:
        """List mail folders"""
        if not self.connection:
            return []
        
        try:
            status, folders = self.connection.list()
            if status == 'OK':
                return [folder.decode() for folder in folders]
        except:
            pass
        
        return []
    
    def select_folder(self, folder: str = 'INBOX') -> int:
        """Select folder and return message count"""
        if not self.connection:
            return 0
        
        try:
            status, data = self.connection.select(folder)
            if status == 'OK':
                return int(data[0])
        except:
            pass
        
        return 0
    
    def fetch_emails(self, folder: str = 'INBOX', limit: int = 10) -> List[Dict]:
        """Fetch emails from folder"""
        if not self.connection:
            return []
        
        emails = []
        
        try:
            # Select folder
            self.select_folder(folder)
            
            # Search for emails
            status, data = self.connection.search(None, 'ALL')
            if status != 'OK':
                return []
            
            email_ids = data[0].split()[-limit:]
            
            for email_id in email_ids:
                # Fetch email
                status, data = self.connection.fetch(email_id, '(RFC822)')
                if status == 'OK':
                    # Parse email (simplified)
                    emails.append({
                        'id': email_id.decode(),
                        'raw': data[0][1]
                    })
        except:
            pass
        
        return emails
    
    def disconnect(self):
        """Disconnect from server"""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

class MailFilter:
    """Email filtering and rules"""
    
    def __init__(self):
        self.rules: List[Dict] = []
    
    def add_rule(self, name: str, condition: Dict, action: Dict):
        """Add filter rule"""
        self.rules.append({
            'name': name,
            'condition': condition,
            'action': action,
            'enabled': True
        })
    
    def apply_rules(self, email: Email) -> List[str]:
        """Apply filter rules to email"""
        actions_taken = []
        
        for rule in self.rules:
            if not rule['enabled']:
                continue
            
            if self._check_condition(email, rule['condition']):
                action = self._apply_action(email, rule['action'])
                if action:
                    actions_taken.append(f"{rule['name']}: {action}")
        
        return actions_taken
    
    def _check_condition(self, email: Email, condition: Dict) -> bool:
        """Check if email matches condition"""
        if 'from' in condition:
            if condition['from'] not in str(email.from_addr):
                return False
        
        if 'subject' in condition:
            if condition['subject'] not in email.subject:
                return False
        
        if 'body' in condition:
            if condition['body'] not in email.body:
                return False
        
        return True
    
    def _apply_action(self, email: Email, action: Dict) -> str:
        """Apply action to email"""
        if action['type'] == 'move':
            return f"Move to {action['folder']}"
        elif action['type'] == 'delete':
            return "Delete"
        elif action['type'] == 'flag':
            return f"Flag as {action['flag']}"
        elif action['type'] == 'forward':
            return f"Forward to {action['to']}"
        
        return ""