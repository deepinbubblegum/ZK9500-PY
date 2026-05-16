import sqlite3
import tempfile
import nbis

class FingerprintMatcher:
    def __init__(self, db_name="fingerprint_db.sqlite"):
        self.db_name = db_name
        settings = nbis.NbisExtractorSettings(
            min_quality=0.0,         
            get_center=False,       
            check_fingerprint=True, 
            compute_nfiq2=False,    
            ppi=500                 
        )
        self.extractor = nbis.new_nbis_extractor(settings)
        
        self._init_db()
        self.memory_cache = []
        self._load_all_to_ram()

    def _init_db(self):
        """Create a new table with a 1-to-Many relationship: 1 user_id can have multiple fingerprint templates"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users_fingerprint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                template BLOB
            )
        ''')
        # create index on user_id column for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON users_fingerprint (user_id)')
        conn.commit()
        conn.close()

    def _load_all_to_ram(self):
        """Load data and group by user_id."""
        self.memory_cache.clear()
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, template FROM users_fingerprint')
        rows = cursor.fetchall()
        conn.close()

        # Create a dictionary and group templates by user_id.
        user_dict = {}
        for row in rows:
            user_id = row[0]
            iso_blob = row[1]
            if iso_blob:
                minutiae_obj = self.extractor.load_iso_19794_2_2005(iso_blob)
                if user_id not in user_dict:
                    user_dict[user_id] = []
                user_dict[user_id].append(minutiae_obj)
        
        # Convert it back to a list and store it in memory_cache.
        for user_id, templates in user_dict.items():
            self.memory_cache.append({
                "user_id": user_id,
                "templates": templates
            })

    def _extract_iso_template_from_bytes(self, image_bytes):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
            temp_file.write(image_bytes)
            temp_file.flush()
            minutiae = self.extractor.extract_minutiae_from_image_file(temp_file.name)
        
        iso_bytes = bytes(minutiae.to_iso_19794_2_2005())
        return iso_bytes

    def enroll(self, user_id: int, list_of_image_bytes: list):
        """supports enrolling with a list of image bytes of any length (from 1 to N)"""
        if not list_of_image_bytes:
            raise ValueError("At least one image is required for enrollment")

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Delete the old data for this user_id first (in case of duplicate registration or updating a new fingerprint).
        cursor.execute('DELETE FROM users_fingerprint WHERE user_id = ?', (user_id,))
        
        # วนลูปบันทึกข้อมูลตามจำนวนรูปที่ถูกส่งเข้ามา
        for img_bytes in list_of_image_bytes:
            iso_blob = self._extract_iso_template_from_bytes(img_bytes)
            cursor.execute('''
                INSERT INTO users_fingerprint (user_id, template)
                VALUES (?, ?)
            ''', (user_id, iso_blob))
            
        conn.commit()
        conn.close()
        
        # โหลดฐานข้อมูลใหม่เข้า RAM ทันที
        self._load_all_to_ram()
        return True

    def add_fingerprints(self, user_id: int, list_of_image_bytes: list):
        """Add new fingerprints to existing user without deleting old ones (non-destructive)"""
        if not list_of_image_bytes:
            raise ValueError("At least one image is required")

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        for img_bytes in list_of_image_bytes:
            iso_blob = self._extract_iso_template_from_bytes(img_bytes)
            cursor.execute('''
                INSERT INTO users_fingerprint (user_id, template)
                VALUES (?, ?)
            ''', (user_id, iso_blob))
            
        conn.commit()
        conn.close()
        
        self._load_all_to_ram()
        return True

    def delete_fingerprint(self, fingerprint_id: int) -> bool:
        """Delete a specific fingerprint record by ID"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users_fingerprint WHERE id = ?', (fingerprint_id,))
        conn.commit()
        deleted_count = cursor.rowcount
        conn.close()
        
        if deleted_count > 0:
            self._load_all_to_ram()
            return True
        return False

    def list_user_fingerprints(self, user_id: int) -> list:
        """Get all fingerprint records for a user. Returns list of dicts with id and count"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users_fingerprint WHERE user_id = ? ORDER BY id', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{"id": row[0]} for row in rows]

    def get_all_users(self) -> list:
        """Get all user IDs in the database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT user_id FROM users_fingerprint ORDER BY user_id')
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]

    def verify(self, new_image_bytes, threshold=35):
        new_iso_bytes = self._extract_iso_template_from_bytes(new_image_bytes)
        new_minutiae = self.extractor.load_iso_19794_2_2005(new_iso_bytes)

        for user in self.memory_cache:
            for base_minutiae in user["templates"]:
                score = base_minutiae.compare(new_minutiae)
                if score >= threshold:
                    return True, user['user_id'], score
                    
        return False, None, 0.0