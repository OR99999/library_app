from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import json
from functools import wraps
import base64

app = Flask(__name__)
app.secret_key = 'library_maroc_2024_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['ID_CARD_FOLDER'] = 'static/id_cards'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ID_CARD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ==================== منع التخزين المؤقت ====================
@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ==================== دالة now() للقوالب ====================
@app.context_processor
def utility_processor():
    return {'now': datetime.now}

# ==================== نماذج قاعدة البيانات ====================

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title_ar = db.Column(db.String(200), nullable=False)
    title_fr = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    author_ar = db.Column(db.String(100), nullable=False)
    author_fr = db.Column(db.String(100), nullable=False)
    author_en = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(200), default='default.png')
    quantity = db.Column(db.Integer, default=1)
    description_ar = db.Column(db.Text, default='')
    description_fr = db.Column(db.Text, default='')
    description_en = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    
    def get_title(self, lang):
        if lang == 'fr':
            return self.title_fr
        elif lang == 'en':
            return self.title_en
        return self.title_ar
    
    def get_author(self, lang):
        if lang == 'fr':
            return self.author_fr
        elif lang == 'en':
            return self.author_en
        return self.author_ar
    
    def get_description(self, lang):
        if lang == 'fr':
            return self.description_fr
        elif lang == 'en':
            return self.description_en
        return self.description_ar

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(100))
    delivery_address = db.Column(db.String(500), nullable=False)
    items = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived_at = db.Column(db.DateTime, nullable=True)

class BorrowOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_name = db.Column(db.String(100), nullable=False)
    member_phone = db.Column(db.String(20), nullable=False)
    member_email = db.Column(db.String(100))
    id_card_number = db.Column(db.String(50), nullable=False)
    id_card_image = db.Column(db.String(200), nullable=True)
    books = db.Column(db.Text, nullable=False)
    borrow_date = db.Column(db.String(50), nullable=False)
    return_date = db.Column(db.String(50), nullable=False)
    total_borrow_price = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived_at = db.Column(db.DateTime, nullable=True)

class InPersonOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_type = db.Column(db.String(20), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.String(500), default='حضوري بالمكتبة')
    items = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    days = db.Column(db.Integer, default=0)
    borrow_date = db.Column(db.String(50), nullable=True)
    return_date = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived_at = db.Column(db.DateTime, nullable=True)

class AdminSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(100), default='admin123')
    borrow_price_per_day = db.Column(db.Float, default=20.0)
    purchase_delivery_fee = db.Column(db.Float, default=30.0)
    borrow_delivery_fee = db.Column(db.Float, default=20.0)
    whatsapp_number = db.Column(db.String(20), default='0655882566')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls(password='admin123', borrow_price_per_day=20.0, 
                          purchase_delivery_fee=30.0, borrow_delivery_fee=20.0,
                          whatsapp_number='0655882566')
            db.session.add(settings)
            db.session.commit()
        return settings

# ==================== إنشاء الكتب ====================

def init_books():
    if Book.query.count() == 0:
        books = [
            Book(title_ar='الخيميائي', title_fr='L\'Alchimiste', title_en='The Alchemist',
                 author_ar='باولو كويلو', author_fr='Paulo Coelho', author_en='Paulo Coelho',
                 category='رواية', price=80.0, image='alchemist.png', quantity=5,
                 description_ar='رواية عالمية تحكي قصة رحلة شاب بحثاً عن كنزه',
                 description_fr='Un roman mondial racontant l\'histoire d\'un jeune homme à la recherche de son trésor',
                 description_en='A worldwide novel about a young man\'s journey in search of his treasure'),
            Book(title_ar='الأجنحة المتكسرة', title_fr='Les Ailes brisées', title_en='Broken Wings',
                 author_ar='جبران خليل جبران', author_fr='Khalil Gibran', author_en='Kahlil Gibran',
                 category='رواية', price=60.0, image='broken-wings.png', quantity=3,
                 description_ar='قصة حب مؤثرة بأسلوب شعري جميل',
                 description_fr='Une histoire d\'amour touchante dans un style poétique',
                 description_en='A touching love story in a beautiful poetic style'),
            Book(title_ar='1984', title_fr='1984', title_en='1984',
                 author_ar='جورج أورويل', author_fr='George Orwell', author_en='George Orwell',
                 category='سياسية', price=70.0, image='1984.png', quantity=4,
                 description_ar='رواية ديستوبيا عن المستقبل والمراقبة',
                 description_fr='Un roman dystopique sur le futur et la surveillance',
                 description_en='A dystopian novel about the future and surveillance'),
            Book(title_ar='البؤساء', title_fr='Les Misérables', title_en='Les Miserables',
                 author_ar='فيكتور هوجو', author_fr='Victor Hugo', author_en='Victor Hugo',
                 category='رواية', price=95.0, image='miserables.png', quantity=3,
                 description_ar='رواية كلاسيكية عن العدالة والحب',
                 description_fr='Un roman classique sur la justice et l\'amour',
                 description_en='A classic novel about justice and love'),
            Book(title_ar='الباحث عن الحقيقة', title_fr='Le Chercheur de vérité', title_en='The Seeker of Truth',
                 author_ar='أحمد زويل', author_fr='Ahmed Zewail', author_en='Ahmed Zewail',
                 category='علمية', price=90.0, image='scientist.png', quantity=2,
                 description_ar='سيرة ذاتية لعالم مصري حصل على جائزة نوبل',
                 description_fr='Autobiographie d\'un scientifique égyptien prix Nobel',
                 description_en='Autobiography of an Egyptian Nobel Prize-winning scientist'),
            Book(title_ar='تاريخ العرب', title_fr='Histoire des Arabes', title_en='History of the Arabs',
                 author_ar='فيليب حتي', author_fr='Philip Hitti', author_en='Philip Hitti',
                 category='تاريخية', price=120.0, image='arab-history.png', quantity=3,
                 description_ar='مرجع شامل لتاريخ العرب والحضارة الإسلامية',
                 description_fr='Une référence complète sur l\'histoire des Arabes et la civilisation islamique',
                 description_en='A comprehensive reference on Arab history and Islamic civilization'),
            Book(title_ar='قصص ما قبل النوم', title_fr='Histoires du coucher', title_en='Bedtime Stories',
                 author_ar='كامل كيلاني', author_fr='Kamel Kilani', author_en='Kamel Kilani',
                 category='أطفال', price=40.0, image='kids-stories.png', quantity=10,
                 description_ar='قصص مسلية للأطفال قبل النوم',
                 description_fr='Des histoires divertissantes pour enfants avant de dormir',
                 description_en='Entertaining stories for children before bedtime'),
            Book(title_ar='سندريلا', title_fr='Cendrillon', title_en='Cinderella',
                 author_ar='شارل بيرو', author_fr='Charles Perrault', author_en='Charles Perrault',
                 category='أطفال', price=35.0, image='cinderella.png', quantity=8,
                 description_ar='قصة الفتاة الجميلة و الحذاء الزجاجي',
                 description_fr='L\'histoire de la belle fille et du soulier de verre',
                 description_en='The story of the beautiful girl and the glass slipper'),
            Book(title_ar='تفسير الجلالين', title_fr='Tafsir Al-Jalalayn', title_en='Tafsir Al-Jalalayn',
                 author_ar='جلال الدين السيوطي', author_fr='Jalal ad-Din as-Suyuti', author_en='Jalal ad-Din as-Suyuti',
                 category='دينية', price=85.0, image='tafseer.png', quantity=4,
                 description_ar='تفسير مبسط للقرآن الكريم',
                 description_fr='Une exégèse simplifiée du Saint Coran',
                 description_en='A simplified interpretation of the Holy Quran'),
            Book(title_ar='فقه السنة', title_fr='Fiqh As-Sunnah', title_en='Fiqh As-Sunnah',
                 author_ar='سيد سابق', author_fr='Sayyid Sabiq', author_en='Sayyid Sabiq',
                 category='دينية', price=110.0, image='fiqh.png', quantity=3,
                 description_ar='شرح مفصل لأحكام الفقه الإسلامي',
                 description_fr='Explication détaillée des règles de la jurisprudence islamique',
                 description_en='Detailed explanation of Islamic jurisprudence rules'),
            Book(title_ar='الأمير الصغير', title_fr='Le Petit Prince', title_en='The Little Prince',
                 author_ar='أنطوان دو سانت إكزوبيري', author_fr='Antoine de Saint-Exupéry', author_en='Antoine de Saint-Exupéry',
                 category='فلسفة', price=45.0, image='little-prince.png', quantity=7,
                 description_ar='قصة فلسفية عن الصداقة والحب',
                 description_fr='Une histoire philosophique sur l\'amitié et l\'amour',
                 description_en='A philosophical story about friendship and love'),
            Book(title_ar='الجمهورية', title_fr='La République', title_en='The Republic',
                 author_ar='أفلاطون', author_fr='Platon', author_en='Plato',
                 category='فلسفة', price=100.0, image='republic.png', quantity=3,
                 description_ar='حوار فلسفي حول العدالة والدولة المثالية',
                 description_fr='Dialogue philosophique sur la justice et l\'État idéal',
                 description_en='Philosophical dialogue about justice and the ideal state'),
        ]
        db.session.add_all(books)
        db.session.commit()

# ==================== الترجمات ====================

translations = {
    'ar': {
        'title': 'مكتبة الغرب',
        'welcome': 'مرحباً بكم في مكتبة الغرب',
        'subtitle': 'آلاف الكتب - خدمة ممتازة - أجواء رائعة',
        'buy': 'شراء',
        'borrow': 'استعارة',
        'search': 'بحث',
        'all': 'الكل',
        'novel': 'رواية',
        'scientific': 'علمية',
        'history': 'تاريخية',
        'kids': 'أطفال',
        'religious': 'دينية',
        'political': 'سياسية',
        'philosophy': 'فلسفة',
        'my_cart': 'سلتي',
        'my_borrow': 'استعاراتي',
        'total': 'المجموع',
        'delivery_fee': 'رسوم التوصيل',
        'grand_total': 'الإجمالي',
        'checkout': 'تأكيد الطلب',
        'name': 'الاسم الكامل',
        'phone': 'رقم الهاتف',
        'email': 'البريد الإلكتروني',
        'address': 'العنوان',
        'id_card': 'رقم البطاقة الوطنية',
        'id_card_image': 'صورة البطاقة الوطنية',
        'borrow_date': 'تاريخ الاستعارة',
        'return_date': 'تاريخ الإرجاع',
        'cancel': 'إلغاء',
        'confirm': 'تأكيد',
        'password': 'كلمة المرور',
        'old_password': 'كلمة المرور القديمة',
        'new_password': 'كلمة المرور الجديدة',
        'confirm_password': 'تأكيد كلمة المرور',
        'order_confirmed': '✅ سيتم تأكيد طلبكم انتظروا من فضلكم',
        'admin_panel': 'لوحة التحكم',
        'dashboard': 'الإحصائيات',
        'purchase_orders': 'طلبات الشراء',
        'borrow_orders': 'طلبات الاستعارة',
        'books': 'الكتب',
        'logout': 'تسجيل خروج',
        'total_revenue': 'إجمالي الإيرادات',
        'pending': 'قيد الانتظار',
        'confirmed': 'مؤكد',
        'delivered': 'تم التسليم',
        'archive': 'أرشيف',
        'search_books': 'بحث عن كتاب...',
        'add_book': 'إضافة كتاب',
        'edit_book': 'تعديل كتاب',
        'delete': 'حذف',
        'title_book': 'عنوان الكتاب',
        'author': 'المؤلف',
        'category': 'التصنيف',
        'price': 'سعر الشراء',
        'quantity': 'العدد',
        'image': 'الصورة',
        'description': 'وصف الكتاب',
        'save': 'حفظ',
        'pending_orders': 'طلبات معلقة',
        'pending_borrows': 'استعارات معلقة',
        'invoice': 'فاتورة شراء',
        'receipt': 'إيصال استعارة',
        'view_id_card': 'عرض البطاقة',
        'edit_dates': 'تعديل التواريخ',
        'new_borrow_date': 'تاريخ استعارة جديد',
        'new_return_date': 'تاريخ إرجاع جديد',
        'update': 'تحديث',
        'available_quantity': 'الكمية المتاحة',
        'select_borrow_date': 'اختر تاريخ الاستعارة',
        'select_return_date': 'اختر تاريخ الإرجاع',
        'borrow_price_per_day': 'سعر الاستعارة لليوم',
        'total_borrow_price': 'إجمالي سعر الاستعارة',
        'number_of_days': 'عدد الأيام',
        'number_of_books': 'عدد الكتب',
        'whatsapp_contact': 'للتواصل عبر واتساب',
        'order_number': 'رقم الطلب',
        'borrow_fee': 'رسوم الاستعارة',
        'filter_type': 'تصفية حسب النوع',
        'all_types': 'الكل',
        'purchase_only': 'طلبات شراء فقط',
        'borrow_only': 'استعارات فقط',
        'whatsapp_number': 'رقم واتساب للتواصل',
        'settings': 'الإعدادات',
        'update_settings': 'تحديث الإعدادات',
        'borrow_price_setting': 'سعر الاستعارة لليوم (درهم)',
        'purchase_delivery_fee_setting': 'سعر توصيل الشراء (درهم)',
        'borrow_delivery_fee_setting': 'سعر توصيل الاستعارة (درهم)',
        'invoice_archive': 'الفاتورة',
        'change_password': 'تغيير كلمة المرور',
        'day': 'يوم',
        'days': 'أيام',
        'in_person_order': 'طلب حضوري',
        'in_person': 'حضوري',
        'print_invoice': 'طباعة الفاتورة',
        'select_order_type': 'نوع الطلب',
        'search_book': 'بحث عن كتاب',
        'add_to_order': 'إضافة إلى الطلب',
        'total_amount': 'المبلغ الإجمالي',
        'no_delivery_fee': 'بدون رسوم توصيل',
        'edit_order': 'تعديل الطلب',
        'archive_order': 'أرشف',
        'order_status': 'حالة الطلب',
        'save_changes': 'حفظ التغييرات',
        'edit_customer': 'تعديل بيانات العميل',
        'confirm_before_print': 'تأكيد قبل الطباعة',
        'waiting_confirmation': 'في انتظار التأكيد',
        'archived': 'مؤرشف',
        'unarchive': 'استعادة',
        'active_orders': 'طلبات نشطة',
        'archived_orders': 'طلبات مؤرشفة',
        'all_orders': 'جميع الطلبات',
        'order_type': 'نوع الطلب',
        'status': 'الحالة',
        'actions': 'الإجراءات',
        'date': 'التاريخ',
        'total_price_label': 'السعر الإجمالي',
        'search_placeholder': '🔍 بحث بالاسم، الهاتف، رقم الطلب، التاريخ...',
        'filter_by_type': 'نوع الطلب:',
        'filter_by_status': 'حالة الطلب:',
        'clear_filters': 'إلغاء الفلترة',
        'all_statuses': 'جميع الحالات',
        'type_purchase': 'شراء',
        'type_borrow': 'استعارة',
        'type_in_person': 'حضوري',
        'returned': 'تم الإرجاع',
        'archived_status': 'مؤرشف',
        'restore': 'استعادة',
        'delete_permanent': 'حذف نهائي',
        'confirm_action': 'تأكيد',
        'archive_action': 'أرشفة',
        'edit_action': 'تعديل',
        'deliver_action': 'تسليم',
        'return_action': 'إرجاع',
        'view_invoice': 'عرض الفاتورة',
        'pending_orders_label': 'طلبات معلقة',
        'active_label': 'نشطة',
        'archived_label': 'مؤرشفة',
        'total_archived': 'إجمالي المؤرشف',
        'completed': 'مكتملة',
        'statistics': 'الإحصائيات',
        'all_orders_count': 'جميع الطلبات',
        'flash_order_confirmed': '✅ تم تأكيد طلب الشراء بنجاح',
        'flash_order_delivered': '✅ تم تسليم الطلب بنجاح',
        'flash_order_deleted': '🗑️ تم حذف طلب الشراء',
        'flash_borrow_confirmed': '✅ تم تأكيد الاستعارة بنجاح',
        'flash_borrow_returned': '📖 تم إرجاع الكتاب بنجاح',
        'flash_borrow_deleted': '🗑️ تم حذف طلب الاستعارة',
        'flash_dates_updated': '📅 تم تعديل تواريخ الاستعارة بنجاح',
        'flash_archived': '📦 تم أرشفة الطلب بنجاح',
        'flash_unarchived': '📂 تم استعادة الطلب من الأرشيف بنجاح',
        'flash_in_person_deleted': '🗑️ تم حذف الطلب الحضوري',
        'flash_in_person_updated': '✅ تم تعديل الطلب الحضوري بنجاح',
        'flash_book_added': '📚 تم إضافة الكتاب بنجاح',
        'flash_book_updated': '📚 تم تعديل الكتاب بنجاح',
        'flash_book_deleted': '📚 تم حذف الكتاب',
        'flash_settings_updated': '⚙️ تم تحديث الإعدادات بنجاح',
        'flash_password_changed': '🔑 تم تغيير كلمة المرور بنجاح',
        'flash_cannot_archive_pending': '⚠️ لا يمكن أرشفة طلب لا يزال قيد الانتظار',
        'flash_cannot_archive_borrow_pending': '⚠️ لا يمكن أرشفة استعارة لا تزال قيد الانتظار',
        'flash_wrong_password': '❌ كلمة المرور غير صحيحة',
        'flash_login_success': '👋 مرحباً بك يا مدير',
        'flash_logout_success': '👋 تم تسجيل الخروج بنجاح',
        'flash_delete_confirm': 'هل أنت متأكد من الحذف؟',
        'flash_archive_confirm': 'هل أنت متأكد من الأرشفة؟',
        'flash_unarchive_confirm': 'هل أنت متأكد من الاستعادة؟',
        'flash_password_mismatch': '❌ كلمة المرور الجديدة غير متطابقة',
        'flash_wrong_old_password': '❌ كلمة المرور القديمة غير صحيحة',
        'flash_password_too_short': '⚠️ كلمة المرور يجب أن تكون 4 أحرف على الأقل',
        'close': 'إغلاق',
        'send_order': 'إرسال الطلب',
        'print': 'طباعة',
        'id_card_placeholder': 'صورة البطاقة الوطنية',
        'empty_cart': 'السلة فارغة',
        'no_results': 'لا توجد نتائج',
        'try_different_keywords': 'جرب كلمات بحث مختلفة',
        'flash_required_fields': '⚠️ الرجاء ملء جميع الحقول',
        'flash_cart_empty': '⚠️ السلة فارغة',
        'flash_added_to_cart': '✅ تم الإضافة إلى السلة',
        'flash_removed_from_cart': '🗑️ تم الإزالة من السلة',
        'flash_unavailable': '⚠️ الكتاب غير متوفر',
        'flash_cannot_exceed_quantity': '⚠️ لا يمكن تجاوز الكمية المتاحة',
        'flash_in_person_created': '✅ تم تسجيل الطلب الحضوري بنجاح',
        'flash_order_submitted': '✅ تم تقديم الطلب بنجاح رقم: {order_id}\n📖 سيتم تأكيد طلبكم انتظروا من فضلكم\n📞 سيتم التواصل معكم عبر واتساب: {whatsapp}',
        'flash_borrow_created': '✅ تم تقديم طلب استعارة بنجاح رقم: {order_id}\n📖 سيتم تأكيد طلبكم انتظروا من فضلكم\n📞 سيتم التواصل معكم عبر واتساب: {whatsapp}',
        'flash_purchase_created': '✅ تم تقديم طلب شراء بنجاح رقم: {order_id}\n📖 سيتم تأكيد طلبكم انتظروا من فضلكم\n📞 سيتم التواصل معكم عبر واتساب: {whatsapp}',
        'flash_required_dates': '⚠️ الرجاء اختيار تاريخ الاستعارة والإرجاع',
        'added': 'تمت الإضافة'
    },
    'fr': {
        'title': 'Bibliothèque Al Gharb',
        'welcome': 'Bienvenue à la Bibliothèque Al Gharb',
        'subtitle': 'Des milliers de livres - Excellent service',
        'buy': 'Acheter',
        'borrow': 'Emprunter',
        'search': 'Rechercher',
        'all': 'Tous',
        'novel': 'Roman',
        'scientific': 'Scientifique',
        'history': 'Histoire',
        'kids': 'Enfants',
        'religious': 'Religieux',
        'political': 'Politique',
        'philosophy': 'Philosophie',
        'my_cart': 'Mon panier',
        'my_borrow': 'Mes emprunts',
        'total': 'Total',
        'delivery_fee': 'Frais de livraison',
        'grand_total': 'Total général',
        'checkout': 'Confirmer',
        'name': 'Nom complet',
        'phone': 'Téléphone',
        'email': 'Email',
        'address': 'Adresse',
        'id_card': 'CIN',
        'id_card_image': 'Photo CIN',
        'borrow_date': "Date d'emprunt",
        'return_date': 'Date de retour',
        'cancel': 'Annuler',
        'confirm': 'Confirmer',
        'password': 'Mot de passe',
        'old_password': 'Ancien mot de passe',
        'new_password': 'Nouveau mot de passe',
        'confirm_password': 'Confirmer le mot de passe',
        'order_confirmed': '✅ Votre commande sera confirmée, veuillez patienter',
        'admin_panel': "Panneau d'administration",
        'dashboard': 'Tableau de bord',
        'purchase_orders': 'Commandes d\'achat',
        'borrow_orders': 'Emprunts',
        'books': 'Livres',
        'logout': 'Déconnexion',
        'total_revenue': 'Revenu total',
        'pending': 'En attente',
        'confirmed': 'Confirmé',
        'delivered': 'Livré',
        'archive': 'Archives',
        'search_books': 'Chercher un livre...',
        'add_book': 'Ajouter un livre',
        'edit_book': 'Modifier',
        'delete': 'Supprimer',
        'title_book': 'Titre',
        'author': 'Auteur',
        'category': 'Catégorie',
        'price': "Prix d'achat",
        'quantity': 'Quantité',
        'image': 'Image',
        'description': 'Description',
        'save': 'Enregistrer',
        'pending_orders': 'Commandes en attente',
        'pending_borrows': 'Emprunts en attente',
        'invoice': "Facture d'achat",
        'receipt': "Reçu d'emprunt",
        'view_id_card': 'Voir CIN',
        'edit_dates': 'Modifier dates',
        'new_borrow_date': "Nouvelle date d'emprunt",
        'new_return_date': 'Nouvelle date de retour',
        'update': 'Mettre à jour',
        'available_quantity': 'Quantité disponible',
        'select_borrow_date': "Choisir la date d'emprunt",
        'select_return_date': 'Choisir la date de retour',
        'borrow_price_per_day': "Prix d'emprunt par jour",
        'total_borrow_price': "Prix total d'emprunt",
        'number_of_days': 'Nombre de jours',
        'number_of_books': 'Nombre de livres',
        'whatsapp_contact': 'Contactez-nous sur WhatsApp',
        'order_number': 'Numéro de commande',
        'borrow_fee': "Frais d'emprunt",
        'filter_type': 'Filtrer par type',
        'all_types': 'Tous',
        'purchase_only': 'Achats seulement',
        'borrow_only': 'Emprunts seulement',
        'whatsapp_number': 'Numéro WhatsApp',
        'settings': 'Paramètres',
        'update_settings': 'Mettre à jour',
        'borrow_price_setting': "Prix d'emprunt par jour (DH)",
        'purchase_delivery_fee_setting': "Frais de livraison achat (DH)",
        'borrow_delivery_fee_setting': "Frais de livraison emprunt (DH)",
        'invoice_archive': 'Facture',
        'change_password': 'Changer mot de passe',
        'day': 'jour',
        'days': 'jours',
        'in_person_order': 'Commande sur place',
        'in_person': 'Sur place',
        'print_invoice': 'Imprimer',
        'select_order_type': 'Type de commande',
        'search_book': 'Chercher un livre',
        'add_to_order': 'Ajouter',
        'total_amount': 'Montant total',
        'no_delivery_fee': 'Sans frais de livraison',
        'edit_order': 'Modifier commande',
        'archive_order': 'Archiver',
        'order_status': 'Statut',
        'save_changes': 'Enregistrer',
        'edit_customer': 'Modifier client',
        'confirm_before_print': 'Confirmer avant impression',
        'waiting_confirmation': 'En attente de confirmation',
        'archived': 'Archivé',
        'unarchive': 'Restaurer',
        'active_orders': 'Commandes actives',
        'archived_orders': 'Commandes archivées',
        'all_orders': 'Toutes les commandes',
        'order_type': 'Type de commande',
        'status': 'Statut',
        'actions': 'Actions',
        'date': 'Date',
        'total_price_label': 'Prix total',
        'search_placeholder': '🔍 Rechercher par nom, téléphone, numéro, date...',
        'filter_by_type': 'Type de commande :',
        'filter_by_status': 'Statut :',
        'clear_filters': 'Effacer les filtres',
        'all_statuses': 'Tous les statuts',
        'type_purchase': 'Achat',
        'type_borrow': 'Emprunt',
        'type_in_person': 'Sur place',
        'returned': 'Retourné',
        'archived_status': 'Archivé',
        'restore': 'Restaurer',
        'delete_permanent': 'Supprimer définitivement',
        'confirm_action': 'Confirmer',
        'archive_action': 'Archiver',
        'edit_action': 'Modifier',
        'deliver_action': 'Livrer',
        'return_action': 'Retourner',
        'view_invoice': 'Voir facture',
        'pending_orders_label': 'Commandes en attente',
        'active_label': 'Actives',
        'archived_label': 'Archivées',
        'total_archived': 'Total archivé',
        'completed': 'Terminées',
        'statistics': 'Statistiques',
        'all_orders_count': 'Toutes les commandes',
        'flash_order_confirmed': '✅ La commande d\'achat a été confirmée avec succès',
        'flash_order_delivered': '✅ La commande a été livrée avec succès',
        'flash_order_deleted': '🗑️ La commande d\'achat a été supprimée',
        'flash_borrow_confirmed': '✅ L\'emprunt a été confirmé avec succès',
        'flash_borrow_returned': '📖 Le livre a été retourné avec succès',
        'flash_borrow_deleted': '🗑️ La demande d\'emprunt a été supprimée',
        'flash_dates_updated': '📅 Les dates d\'emprunt ont été modifiées avec succès',
        'flash_archived': '📦 La commande a été archivée avec succès',
        'flash_unarchived': '📂 La commande a été restaurée des archives avec succès',
        'flash_in_person_deleted': '🗑️ La commande sur place a été supprimée',
        'flash_in_person_updated': '✅ La commande sur place a été modifiée avec succès',
        'flash_book_added': '📚 Le livre a été ajouté avec succès',
        'flash_book_updated': '📚 Le livre a été modifié avec succès',
        'flash_book_deleted': '📚 Le livre a été supprimé',
        'flash_settings_updated': '⚙️ Les paramètres ont été mis à jour avec succès',
        'flash_password_changed': '🔑 Le mot de passe a été changé avec succès',
        'flash_cannot_archive_pending': '⚠️ Impossible d\'archiver une commande en attente',
        'flash_cannot_archive_borrow_pending': '⚠️ Impossible d\'archiver un emprunt en attente',
        'flash_wrong_password': '❌ Mot de passe incorrect',
        'flash_login_success': '👋 Bienvenue administrateur',
        'flash_logout_success': '👋 Déconnexion réussie',
        'flash_delete_confirm': 'Êtes-vous sûr de vouloir supprimer ?',
        'flash_archive_confirm': 'Êtes-vous sûr de vouloir archiver ?',
        'flash_unarchive_confirm': 'Êtes-vous sûr de vouloir restaurer ?',
        'flash_password_mismatch': '❌ Les mots de passe ne correspondent pas',
        'flash_wrong_old_password': '❌ Ancien mot de passe incorrect',
        'flash_password_too_short': '⚠️ Le mot de passe doit comporter au moins 4 caractères',
        'close': 'Fermer',
        'send_order': 'Envoyer la commande',
        'print': 'Imprimer',
        'id_card_placeholder': 'Photo de la carte d\'identité',
        'empty_cart': 'Le panier est vide',
        'no_results': 'Aucun résultat',
        'try_different_keywords': 'Essayez d\'autres mots-clés',
        'flash_required_fields': '⚠️ Veuillez remplir tous les champs',
        'flash_cart_empty': '⚠️ Le panier est vide',
        'flash_added_to_cart': '✅ Ajouté au panier',
        'flash_removed_from_cart': '🗑️ Retiré du panier',
        'flash_unavailable': '⚠️ Livre indisponible',
        'flash_cannot_exceed_quantity': '⚠️ Impossible de dépasser la quantité disponible',
        'flash_in_person_created': '✅ Commande sur place enregistrée avec succès',
        'flash_order_submitted': '✅ Commande soumise avec succès N°: {order_id}\n📖 Votre commande sera confirmée, veuillez patienter\n📞 Nous vous contacterons via WhatsApp: {whatsapp}',
        'flash_borrow_created': '✅ Demande d\'emprunt soumise avec succès N°: {order_id}\n📖 Votre demande sera confirmée, veuillez patienter\n📞 Nous vous contacterons via WhatsApp: {whatsapp}',
        'flash_purchase_created': '✅ Commande d\'achat soumise avec succès N°: {order_id}\n📖 Votre commande sera confirmée, veuillez patienter\n📞 Nous vous contacterons via WhatsApp: {whatsapp}',
        'flash_required_dates': '⚠️ Veuillez choisir les dates d\'emprunt et de retour',
        'added': 'Ajouté'
    },
    'en': {
        'title': 'Al Gharb Library',
        'welcome': 'Welcome to Al Gharb Library',
        'subtitle': 'Thousands of books - Excellent service',
        'buy': 'Buy',
        'borrow': 'Borrow',
        'search': 'Search',
        'all': 'All',
        'novel': 'Novel',
        'scientific': 'Scientific',
        'history': 'History',
        'kids': 'Kids',
        'religious': 'Religious',
        'political': 'Political',
        'philosophy': 'Philosophy',
        'my_cart': 'My Cart',
        'my_borrow': 'My Borrowings',
        'total': 'Total',
        'delivery_fee': 'Delivery Fee',
        'grand_total': 'Grand Total',
        'checkout': 'Checkout',
        'name': 'Full Name',
        'phone': 'Phone',
        'email': 'Email',
        'address': 'Address',
        'id_card': 'ID Card Number',
        'id_card_image': 'ID Card Image',
        'borrow_date': 'Borrow Date',
        'return_date': 'Return Date',
        'cancel': 'Cancel',
        'confirm': 'Confirm',
        'password': 'Password',
        'old_password': 'Old Password',
        'new_password': 'New Password',
        'confirm_password': 'Confirm Password',
        'order_confirmed': '✅ Your order will be confirmed, please wait',
        'admin_panel': 'Admin Panel',
        'dashboard': 'Dashboard',
        'purchase_orders': 'Purchase Orders',
        'borrow_orders': 'Borrow Orders',
        'books': 'Books',
        'logout': 'Logout',
        'total_revenue': 'Total Revenue',
        'pending': 'Pending',
        'confirmed': 'Confirmed',
        'delivered': 'Delivered',
        'archive': 'Archive',
        'search_books': 'Search books...',
        'add_book': 'Add Book',
        'edit_book': 'Edit Book',
        'delete': 'Delete',
        'title_book': 'Title',
        'author': 'Author',
        'category': 'Category',
        'price': 'Purchase Price',
        'quantity': 'Quantity',
        'image': 'Image',
        'description': 'Description',
        'save': 'Save',
        'pending_orders': 'Pending Orders',
        'pending_borrows': 'Pending Borrowings',
        'invoice': 'Purchase Invoice',
        'receipt': 'Borrow Receipt',
        'view_id_card': 'View ID Card',
        'edit_dates': 'Edit Dates',
        'new_borrow_date': 'New Borrow Date',
        'new_return_date': 'New Return Date',
        'update': 'Update',
        'available_quantity': 'Available Quantity',
        'select_borrow_date': 'Select Borrow Date',
        'select_return_date': 'Select Return Date',
        'borrow_price_per_day': 'Borrow Price Per Day',
        'total_borrow_price': 'Total Borrow Price',
        'number_of_days': 'Number of Days',
        'number_of_books': 'Number of Books',
        'whatsapp_contact': 'Contact us on WhatsApp',
        'order_number': 'Order Number',
        'borrow_fee': 'Borrow Fee',
        'filter_type': 'Filter by type',
        'all_types': 'All',
        'purchase_only': 'Purchases only',
        'borrow_only': 'Borrowings only',
        'whatsapp_number': 'WhatsApp Number',
        'settings': 'Settings',
        'update_settings': 'Update Settings',
        'borrow_price_setting': 'Borrow Price Per Day (DH)',
        'purchase_delivery_fee_setting': 'Purchase Delivery Fee (DH)',
        'borrow_delivery_fee_setting': 'Borrow Delivery Fee (DH)',
        'invoice_archive': 'Invoice',
        'change_password': 'Change Password',
        'day': 'day',
        'days': 'days',
        'in_person_order': 'In-Person Order',
        'in_person': 'In Person',
        'print_invoice': 'Print Invoice',
        'select_order_type': 'Order Type',
        'search_book': 'Search Book',
        'add_to_order': 'Add to Order',
        'total_amount': 'Total Amount',
        'no_delivery_fee': 'No delivery fee',
        'edit_order': 'Edit Order',
        'archive_order': 'Archive',
        'order_status': 'Status',
        'save_changes': 'Save Changes',
        'edit_customer': 'Edit Customer',
        'confirm_before_print': 'Confirm before printing',
        'waiting_confirmation': 'Waiting for confirmation',
        'archived': 'Archived',
        'unarchive': 'Restore',
        'active_orders': 'Active Orders',
        'archived_orders': 'Archived Orders',
        'all_orders': 'All Orders',
        'order_type': 'Order Type',
        'status': 'Status',
        'actions': 'Actions',
        'date': 'Date',
        'total_price_label': 'Total Price',
        'search_placeholder': '🔍 Search by name, phone, order number, date...',
        'filter_by_type': 'Order Type:',
        'filter_by_status': 'Status:',
        'clear_filters': 'Clear Filters',
        'all_statuses': 'All Statuses',
        'type_purchase': 'Purchase',
        'type_borrow': 'Borrow',
        'type_in_person': 'In Person',
        'returned': 'Returned',
        'archived_status': 'Archived',
        'restore': 'Restore',
        'delete_permanent': 'Delete Permanent',
        'confirm_action': 'Confirm',
        'archive_action': 'Archive',
        'edit_action': 'Edit',
        'deliver_action': 'Deliver',
        'return_action': 'Return',
        'view_invoice': 'View Invoice',
        'pending_orders_label': 'Pending Orders',
        'active_label': 'Active',
        'archived_label': 'Archived',
        'total_archived': 'Total Archived',
        'completed': 'Completed',
        'statistics': 'Statistics',
        'all_orders_count': 'All Orders',
        'flash_order_confirmed': '✅ Purchase order confirmed successfully',
        'flash_order_delivered': '✅ Order delivered successfully',
        'flash_order_deleted': '🗑️ Purchase order deleted',
        'flash_borrow_confirmed': '✅ Borrowing confirmed successfully',
        'flash_borrow_returned': '📖 Book returned successfully',
        'flash_borrow_deleted': '🗑️ Borrow request deleted',
        'flash_dates_updated': '📅 Borrow dates updated successfully',
        'flash_archived': '📦 Order archived successfully',
        'flash_unarchived': '📂 Order restored from archive successfully',
        'flash_in_person_deleted': '🗑️ In-person order deleted',
        'flash_in_person_updated': '✅ In-person order updated successfully',
        'flash_book_added': '📚 Book added successfully',
        'flash_book_updated': '📚 Book updated successfully',
        'flash_book_deleted': '📚 Book deleted',
        'flash_settings_updated': '⚙️ Settings updated successfully',
        'flash_password_changed': '🔑 Password changed successfully',
        'flash_cannot_archive_pending': '⚠️ Cannot archive a pending order',
        'flash_cannot_archive_borrow_pending': '⚠️ Cannot archive a pending borrowing',
        'flash_wrong_password': '❌ Incorrect password',
        'flash_login_success': '👋 Welcome admin',
        'flash_logout_success': '👋 Logged out successfully',
        'flash_delete_confirm': 'Are you sure you want to delete?',
        'flash_archive_confirm': 'Are you sure you want to archive?',
        'flash_unarchive_confirm': 'Are you sure you want to restore?',
        'flash_password_mismatch': '❌ Passwords do not match',
        'flash_wrong_old_password': '❌ Old password is incorrect',
        'flash_password_too_short': '⚠️ Password must be at least 4 characters',
        'close': 'Close',
        'send_order': 'Send Order',
        'print': 'Print',
        'id_card_placeholder': 'ID Card Image',
        'empty_cart': 'Cart is empty',
        'no_results': 'No results',
        'try_different_keywords': 'Try different keywords',
        'flash_required_fields': '⚠️ Please fill all fields',
        'flash_cart_empty': '⚠️ Cart is empty',
        'flash_added_to_cart': '✅ Added to cart',
        'flash_removed_from_cart': '🗑️ Removed from cart',
        'flash_unavailable': '⚠️ Book is not available',
        'flash_cannot_exceed_quantity': '⚠️ Cannot exceed available quantity',
        'flash_in_person_created': '✅ In-person order created successfully',
        'flash_order_submitted': '✅ Order submitted successfully #: {order_id}\n📖 Your order will be confirmed, please wait\n📞 We will contact you via WhatsApp: {whatsapp}',
        'flash_borrow_created': '✅ Borrow request submitted successfully #: {order_id}\n📖 Your request will be confirmed, please wait\n📞 We will contact you via WhatsApp: {whatsapp}',
        'flash_purchase_created': '✅ Purchase order submitted successfully #: {order_id}\n📖 Your order will be confirmed, please wait\n📞 We will contact you via WhatsApp: {whatsapp}',
        'flash_required_dates': '⚠️ Please select borrow and return dates',
        'added': 'Added'
    }
}

# ==================== تصفية JSON ====================
@app.template_filter('fromjson')
def from_json_filter(value):
    import json
    try:
        return json.loads(value)
    except:
        return []

# ==================== دالة التحقق ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('الرجاء تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== حساب سعر الاستعارة ====================

def calculate_borrow_price(borrow_date, return_date, settings, items):
    start = datetime.strptime(borrow_date, '%Y-%m-%d')
    end = datetime.strptime(return_date, '%Y-%m-%d')
    days = max((end - start).days, 1)
    total_books = sum(item.get('quantity', 1) for item in items)
    borrow_price = (days * settings.borrow_price_per_day) * total_books
    return borrow_price + settings.borrow_delivery_fee

# ==================== دالة ترتيب الطلبات ====================
def sort_orders_by_status(orders):
    """ترتيب الطلبات بحيث تظهر 'pending' في الأعلى"""
    status_priority = {'pending': 0, 'confirmed': 1, 'delivered': 2, 'returned': 2, 'archived': 3}
    return sorted(orders, key=lambda x: status_priority.get(x.status, 10))

# ==================== دوال الفواتير ====================

def generate_purchase_invoice_html(order, settings, lang='ar', is_archived=False):
    items = json.loads(order.items)
    products_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
    
    delivery_fee = settings.purchase_delivery_fee
    whatsapp = settings.whatsapp_number
    order_id = order.id
    
    t = translations.get(lang, translations['ar'])
    
    title_text = 'فاتورة شراء' if lang == 'ar' else 'Facture d\'achat' if lang == 'fr' else 'Purchase Invoice'
    header_text = 'فاتورة شراء' if lang == 'ar' else 'Facture d\'achat' if lang == 'fr' else 'Purchase Invoice'
    order_label = t.get('order_number', 'رقم الطلب')
    date_label = t.get('date', 'التاريخ')
    customer_label = t.get('name', 'العميل')
    phone_label = t.get('phone', 'الهاتف')
    address_label = t.get('address', 'العنوان')
    book_label = t.get('title_book', 'الكتاب')
    qty_label = t.get('quantity', 'الكمية')
    price_label = t.get('price', 'السعر')
    total_label = t.get('total', 'الإجمالي')
    subtotal_label = t.get('total', 'المجموع')
    delivery_label = t.get('delivery_fee', 'رسوم التوصيل')
    grand_total_label = t.get('grand_total', 'الإجمالي')
    thank_you = 'شكراً لشرائكم من مكتبة الغرب' if lang == 'ar' else 'Merci pour votre achat à la Bibliothèque Al Gharb' if lang == 'fr' else 'Thank you for your purchase from Al Gharb Library'
    contact_label = t.get('whatsapp_contact', 'للتواصل عبر واتساب')
    print_label = t.get('print', 'طباعة')
    close_label = t.get('close', 'إغلاق')
    
    items_html = ''
    for idx, item in enumerate(items, 1):
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        item_total = price * qty
        items_html += f'<tr><td style="text-align:center">{idx}</td><td style="text-align:center">{item.get("name", "")}</td><td style="text-align:center">{qty}</td><td style="text-align:center">{price} DH</td><td style="text-align:center">{item_total} DH</td></tr>'
    
    return f'''<!DOCTYPE html>
    <html dir="{'rtl' if lang == 'ar' else 'ltr'}" lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <title>{title_text} #{order_id}</title>
        <style>
            @media print {{ .no-print {{ display: none; }} }}
            body {{ font-family: 'Cairo', Arial, sans-serif; padding: 20px; background: #EFEBE9; }}
            .invoice {{ max-width: 600px; margin: auto; background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #D4A043; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h2 {{ color: #5D4037; margin: 0; }}
            .info {{ margin-bottom: 20px; line-height: 1.8; background: #f9f9f9; padding: 10px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #5D4037; color: white; padding: 10px; border: 1px solid #ddd; }}
            td {{ padding: 8px; border: 1px solid #ddd; text-align: center; }}
            .total {{ font-size: 16px; font-weight: bold; text-align: left; border-top: 2px solid #D4A043; padding-top: 10px; margin-top: 10px; background: #FFF8E1; padding: 10px; border-radius: 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            button {{ background: #5D4037; color: white; border: none; padding: 10px 20px; margin: 5px; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="invoice">
            <div class="header"><h2>📚 مكتبة الغرب / Al Gharb Library</h2><p>{header_text}</p></div>
            <div class="info">
                <p><strong>{order_label}:</strong> #{order_id}</p>
                <p><strong>{date_label}:</strong> {order.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>{customer_label}:</strong> {order.customer_name}</p>
                <p><strong>{phone_label}:</strong> {order.customer_phone}</p>
                <p><strong>{address_label}:</strong> {order.delivery_address}</p>
            </div>
            <table>
                <thead><tr><th>#</th><th>{book_label}</th><th>{qty_label}</th><th>{price_label}</th><th>{total_label}</th></tr></thead>
                <tbody>{items_html}</tbody>
            </table>
            <div class="total">
                <div>{subtotal_label}: {products_total} DH</div>
                <div>{delivery_label}: {delivery_fee} DH</div>
                <div style="font-size:20px; color:#D4A043;">{grand_total_label}: {order.total_price} DH</div>
            </div>
            <div class="footer"><p>{thank_you} 🤍</p><p>{contact_label}: {whatsapp}</p></div>
            <div class="no-print"><button onclick="window.print()">🖨️ {print_label}</button><button onclick="window.close()">❌ {close_label}</button></div>
        </div>
    </body>
    </html>'''

def generate_borrow_invoice_html(order, settings, lang='ar', is_archived=False):
    if hasattr(order, 'books'):
        items = json.loads(order.books)
    else:
        items = json.loads(order.items)
    
    borrow_date = order.borrow_date
    return_date = order.return_date
    
    start = datetime.strptime(borrow_date, '%Y-%m-%d')
    end = datetime.strptime(return_date, '%Y-%m-%d')
    days = max((end - start).days, 1)
    total_books = sum(item.get('quantity', 1) for item in items)
    
    borrow_price_per_day = settings.borrow_price_per_day
    borrow_delivery_fee = settings.borrow_delivery_fee
    whatsapp = settings.whatsapp_number
    
    borrow_days_price = (days * borrow_price_per_day) * total_books
    total_borrow_price = borrow_days_price + borrow_delivery_fee
    
    order_id = order.id
    
    if hasattr(order, 'member_name'):
        customer_name = order.member_name
        customer_phone = order.member_phone
        id_card_number = order.id_card_number
    else:
        customer_name = order.customer_name
        customer_phone = order.customer_phone
        id_card_number = getattr(order, 'id_card_number', '-')
    
    t = translations.get(lang, translations['ar'])
    
    title_text = 'إيصال استعارة' if lang == 'ar' else 'Reçu d\'emprunt' if lang == 'fr' else 'Borrow Receipt'
    header_text = 'إيصال استعارة' if lang == 'ar' else 'Reçu d\'emprunt' if lang == 'fr' else 'Borrow Receipt'
    order_label = t.get('order_number', 'رقم الطلب')
    borrow_date_label = t.get('borrow_date', 'تاريخ الاستعارة')
    return_date_label = t.get('return_date', 'تاريخ الإرجاع')
    days_label = t.get('number_of_days', 'عدد الأيام')
    books_label = t.get('number_of_books', 'عدد الكتب')
    customer_label = t.get('name', 'المستعير')
    phone_label = t.get('phone', 'الهاتف')
    id_card_label = t.get('id_card', 'رقم البطاقة')
    book_label = t.get('title_book', 'الكتاب')
    author_label = t.get('author', 'المؤلف')
    qty_label = t.get('quantity', 'الكمية')
    price_label = t.get('price', 'سعر الكتاب')
    total_label = t.get('total', 'الإجمالي')
    borrow_price_label = t.get('borrow_price_per_day', 'سعر الاستعارة لليوم')
    borrow_fee_label = t.get('borrow_fee', 'رسوم الاستعارة')
    delivery_label = t.get('delivery_fee', 'رسوم التوصيل')
    grand_total_label = t.get('total_borrow_price', 'إجمالي رسوم الاستعارة')
    thank_you = 'شكراً لثقتكم بمكتبة الغرب' if lang == 'ar' else 'Merci pour votre confiance en la Bibliothèque Al Gharb' if lang == 'fr' else 'Thank you for trusting Al Gharb Library'
    contact_label = t.get('whatsapp_contact', 'للتواصل عبر واتساب')
    print_label = t.get('print', 'طباعة')
    close_label = t.get('close', 'إغلاق')
    warning_text = '⚠️ يجب إرجاع الكتب في تاريخ الاستحقاق' if lang == 'ar' else '⚠️ Les livres doivent être retournés à la date d\'échéance' if lang == 'fr' else '⚠️ Books must be returned on the due date'
    
    items_html = ''
    for idx, item in enumerate(items, 1):
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        author = item.get('author', '')
        book_name = item.get('name', '')
        item_total = price * qty
        items_html += f'<tr><td style="text-align:center">{idx}</td><td style="text-align:center">{book_name}</td><td style="text-align:center">{author}</td><td style="text-align:center">{qty}</td><td style="text-align:center">{price} DH</td><td style="text-align:center">{item_total} DH</td></tr>'
    
    return f'''<!DOCTYPE html>
    <html dir="{'rtl' if lang == 'ar' else 'ltr'}" lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <title>{title_text} #{order_id}</title>
        <style>
            @media print {{ .no-print {{ display: none; }} }}
            body {{ font-family: 'Cairo', Arial, sans-serif; padding: 20px; background: #EFEBE9; }}
            .invoice {{ max-width: 650px; margin: auto; background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #D4A043; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h2 {{ color: #5D4037; margin: 0; }}
            .info {{ margin-bottom: 20px; line-height: 1.8; background: #f9f9f9; padding: 10px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #5D4037; color: white; padding: 10px; border: 1px solid #ddd; }}
            td {{ padding: 8px; border: 1px solid #ddd; text-align: center; }}
            .total {{ font-size: 16px; font-weight: bold; text-align: left; border-top: 2px solid #D4A043; padding-top: 10px; margin-top: 10px; background: #FFF8E1; padding: 10px; border-radius: 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            button {{ background: #5D4037; color: white; border: none; padding: 10px 20px; margin: 5px; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="invoice">
            <div class="header"><h2>📚 مكتبة الغرب / Al Gharb Library</h2><p>{header_text}</p></div>
            <div class="info">
                <p><strong>{order_label}:</strong> #{order_id}</p>
                <p><strong>{borrow_date_label}:</strong> {borrow_date}</p>
                <p><strong>{return_date_label}:</strong> {return_date}</p>
                <p><strong>{days_label}:</strong> {days} {'أيام' if lang == 'ar' and days > 1 else 'يوم' if lang == 'ar' else 'jours' if lang == 'fr' and days > 1 else 'jour' if lang == 'fr' else 'days' if days > 1 else 'day'}</p>
                <p><strong>{books_label}:</strong> {total_books}</p>
                <p><strong>{customer_label}:</strong> {customer_name}</p>
                <p><strong>{phone_label}:</strong> {customer_phone}</p>
                <p><strong>{id_card_label}:</strong> {id_card_number}</p>
            </div>
            <table>
                <thead><tr><th>#</th><th>{book_label}</th><th>{author_label}</th><th>{qty_label}</th><th>{price_label}</th><th>{total_label}</th></tr></thead>
                <tbody>{items_html}</tbody>
            </table>
            <div class="total">
                <div>{borrow_price_label}: {borrow_price_per_day} DH</div>
                <div>{days_label}: {days} × {total_books}</div>
                <div>{borrow_fee_label}: {borrow_days_price} DH</div>
                <div>{delivery_label}: {borrow_delivery_fee} DH</div>
                <div style="font-size:20px; color:#D4A043;">{grand_total_label}: {total_borrow_price} DH</div>
            </div>
            <div class="footer"><p>{warning_text}</p><p>{thank_you} 🤍</p><p>{contact_label}: {whatsapp}</p></div>
            <div class="no-print"><button onclick="window.print()">🖨️ {print_label}</button><button onclick="window.close()">❌ {close_label}</button></div>
        </div>
    </body>
    </html>'''

def generate_in_person_invoice_html(order, settings, lang='ar'):
    items = json.loads(order.items)
    total = 0
    items_html = ''
    
    order_id = order.id
    t = translations.get(lang, translations['ar'])
    
    title_text = 'فاتورة شراء حضوري' if order.order_type == 'purchase' else 'إيصال استعارة حضوري'
    if lang == 'fr':
        title_text = 'Facture d\'achat sur place' if order.order_type == 'purchase' else 'Reçu d\'emprunt sur place'
    elif lang == 'en':
        title_text = 'In-Person Purchase Invoice' if order.order_type == 'purchase' else 'In-Person Borrow Receipt'
    
    order_label = t.get('order_number', 'رقم الطلب')
    date_label = t.get('date', 'التاريخ')
    customer_label = t.get('name', 'العميل')
    phone_label = t.get('phone', 'الهاتف')
    address_label = t.get('address', 'العنوان')
    book_label = t.get('title_book', 'الكتاب')
    qty_label = t.get('quantity', 'الكمية')
    price_label = t.get('price', 'السعر')
    total_label = t.get('total', 'الإجمالي')
    grand_total_label = t.get('total_amount', 'الإجمالي')
    no_delivery = t.get('no_delivery_fee', 'بدون رسوم توصيل')
    thank_you = 'شكراً لثقتكم بمكتبة الغرب' if lang == 'ar' else 'Merci pour votre confiance en la Bibliothèque Al Gharb' if lang == 'fr' else 'Thank you for trusting Al Gharb Library'
    print_label = t.get('print', 'طباعة')
    close_label = t.get('close', 'إغلاق')
    
    for idx, item in enumerate(items, 1):
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        if order.order_type == 'borrow' and order.days > 0:
            item_total = (settings.borrow_price_per_day * order.days) * qty
            display_price = settings.borrow_price_per_day
        else:
            item_total = price * qty
            display_price = price
        total += item_total
        items_html += f'<tr><td style="text-align:center">{idx}</td><td style="text-align:center">{item.get("name", "")}</td><td style="text-align:center">{qty}</td><td style="text-align:center">{display_price} DH</td><td style="text-align:center">{item_total} DH</td></tr>'
    
    borrow_info = ''
    if order.order_type == 'borrow' and order.days > 0:
        borrow_date_label = t.get('borrow_date', 'تاريخ الاستعارة')
        return_date_label = t.get('return_date', 'تاريخ الإرجاع')
        days_label = t.get('number_of_days', 'عدد الأيام')
        books_label = t.get('number_of_books', 'عدد الكتب')
        price_per_day_label = t.get('borrow_price_per_day', 'سعر اليوم للكتاب')
        borrow_date = order.borrow_date or datetime.now().strftime('%Y-%m-%d')
        return_date = order.return_date or (datetime.now() + timedelta(days=order.days)).strftime('%Y-%m-%d')
        total_books = sum(item.get('quantity', 1) for item in items)
        borrow_info = f'''
            <div class="borrow-info" style="background:#FFF8E1; padding:10px; border-radius:10px; margin-bottom:15px;">
                <p><strong>📅 {borrow_date_label}:</strong> {borrow_date}</p>
                <p><strong>📅 {return_date_label}:</strong> {return_date}</p>
                <p><strong>📆 {days_label}:</strong> {order.days} {'أيام' if lang == 'ar' and order.days > 1 else 'يوم' if lang == 'ar' else 'jours' if lang == 'fr' and order.days > 1 else 'jour' if lang == 'fr' else 'days' if order.days > 1 else 'day'}</p>
                <p><strong>📚 {books_label}:</strong> {total_books}</p>
                <p><strong>💰 {price_per_day_label}:</strong> {settings.borrow_price_per_day} DH</p>
            </div>
        '''
    
    return f'''<!DOCTYPE html>
    <html dir="{'rtl' if lang == 'ar' else 'ltr'}" lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <title>{title_text} #{order_id}</title>
        <style>
            @media print {{ .no-print {{ display: none; }} }}
            body {{ font-family: 'Cairo', Arial, sans-serif; padding: 20px; background: #EFEBE9; }}
            .invoice {{ max-width: 600px; margin: auto; background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #D4A043; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h2 {{ color: #5D4037; margin: 0; }}
            .info {{ margin-bottom: 20px; line-height: 1.8; background: #f9f9f9; padding: 10px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #5D4037; color: white; padding: 10px; border: 1px solid #ddd; }}
            td {{ padding: 8px; border: 1px solid #ddd; text-align: center; }}
            .total {{ font-size: 16px; font-weight: bold; text-align: left; border-top: 2px solid #D4A043; padding-top: 10px; margin-top: 10px; background: #FFF8E1; padding: 10px; border-radius: 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            button {{ background: #5D4037; color: white; border: none; padding: 10px 20px; margin: 5px; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="invoice">
            <div class="header"><h2>📚 مكتبة الغرب / Al Gharb Library</h2><p>{title_text}</p></div>
            <div class="info">
                <p><strong>{order_label}:</strong> #{order_id}</p>
                <p><strong>{date_label}:</strong> {order.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>{customer_label}:</strong> {order.customer_name}</p>
                <p><strong>{phone_label}:</strong> {order.customer_phone}</p>
                <p><strong>{address_label}:</strong> {order.customer_address}</p>
            </div>
            {borrow_info}
            <table>
                <thead><tr><th>#</th><th>{book_label}</th><th>{qty_label}</th><th>{price_label}</th><th>{total_label}</th></tr></thead>
                <tbody>{items_html}</tbody>
            </table>
            <div class="total">
                <div style="font-size:20px; color:#D4A043;">{grand_total_label}: {total} DH</div>
                <div>{no_delivery}</div>
            </div>
            <div class="footer"><p>{thank_you} 🤍</p></div>
            <div class="no-print"><button onclick="window.print()">🖨️ {print_label}</button><button onclick="window.close()">❌ {close_label}</button></div>
        </div>
    </body>
    </html>'''

# ==================== مسارات الفواتير ====================

@app.route('/invoice/show/<order_type>/<int:order_id>')
def show_invoice(order_type, order_id):
    lang = session.get('lang', 'ar')
    settings = AdminSettings.get()
    
    if order_type == 'purchase':
        order = PurchaseOrder.query.get_or_404(order_id)
        return generate_purchase_invoice_html(order, settings, lang, is_archived=False)
    elif order_type == 'borrow':
        order = BorrowOrder.query.get_or_404(order_id)
        return generate_borrow_invoice_html(order, settings, lang, is_archived=False)
    elif order_type == 'in_person':
        order = InPersonOrder.query.get_or_404(order_id)
        return generate_in_person_invoice_html(order, settings, lang)
    else:
        return "نوع الطلب غير صحيح"

@app.route('/invoice/purchase/<int:id>')
def invoice_purchase(id):
    lang = session.get('lang', 'ar')
    order = PurchaseOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_purchase_invoice_html(order, settings, lang, is_archived=False)

@app.route('/invoice/borrow/<int:id>')
def invoice_borrow(id):
    lang = session.get('lang', 'ar')
    borrow = BorrowOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_borrow_invoice_html(borrow, settings, lang, is_archived=False)

@app.route('/invoice/in_person/<int:id>')
def invoice_in_person(id):
    lang = session.get('lang', 'ar')
    order = InPersonOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_in_person_invoice_html(order, settings, lang)

@app.route('/invoice/archive/purchase/<int:id>')
def invoice_archive_purchase(id):
    lang = session.get('lang', 'ar')
    order = PurchaseOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_purchase_invoice_html(order, settings, lang, is_archived=False)

@app.route('/invoice/archive/borrow/<int:id>')
def invoice_archive_borrow(id):
    lang = session.get('lang', 'ar')
    order = BorrowOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_borrow_invoice_html(order, settings, lang, is_archived=False)

@app.route('/invoice/archive/in_person/<int:id>')
def invoice_archive_in_person(id):
    lang = session.get('lang', 'ar')
    order = InPersonOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    return generate_in_person_invoice_html(order, settings, lang)

# ==================== المسارات الأساسية ====================

@app.route('/')
def home():
    lang = session.get('lang', 'ar')
    is_admin = session.get('admin_logged_in', False)
    books = Book.query.filter_by(is_active=True).all()
    today = datetime.now().strftime('%Y-%m-%d')
    default_return = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    settings = AdminSettings.get()
    return render_template('index.html', lang=lang, t=translations[lang], is_admin=is_admin, books=books, 
                          today=today, default_return=default_return, settings=settings)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['ar', 'fr', 'en']:
        session['lang'] = lang
    return redirect(url_for('home'))

# ==================== شراء الكتب ====================

@app.route('/purchase/order', methods=['POST'])
def purchase_order():
    lang = session.get('lang', 'ar')
    data = request.get_json()
    settings = AdminSettings.get()
    
    session.pop('last_order_id', None)
    session.pop('current_invoice_id', None)
    
    items = data.get('items', [])
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            if item.get('quantity', 1) > book.quantity:
                return jsonify({'success': False, 'message': f'الكمية المطلوبة من كتاب "{book.get_title(lang)}" أكبر من المتاحة ({book.quantity})'})
    
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            book.quantity -= item.get('quantity', 1)
    
    total_products = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
    total_price = total_products + settings.purchase_delivery_fee
    
    new_order = PurchaseOrder(
        customer_name=data.get('name'),
        customer_phone=data.get('phone'),
        customer_email=data.get('email'),
        delivery_address=data.get('address'),
        items=json.dumps(items),
        total_price=total_price,
        status='pending'
    )
    db.session.add(new_order)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': translations[lang]['order_confirmed'], 
        'order_id': new_order.id,
        'invoice_url': f'/invoice/show/purchase/{new_order.id}'
    })

# ==================== استعارة الكتب ====================

@app.route('/borrow/order', methods=['POST'])
def borrow_order():
    lang = session.get('lang', 'ar')
    data = request.get_json()
    settings = AdminSettings.get()
    
    session.pop('last_order_id', None)
    session.pop('current_invoice_id', None)
    
    items = data.get('items', [])
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            if item.get('quantity', 1) > book.quantity:
                return jsonify({'success': False, 'message': f'الكمية المطلوبة من كتاب "{book.get_title(lang)}" أكبر من المتاحة ({book.quantity})'})
    
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            book.quantity -= item.get('quantity', 1)
    
    id_card_image = None
    if 'id_card_image' in data and data['id_card_image']:
        try:
            image_data = data['id_card_image']
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            filename = f"id_card_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            filepath = os.path.join(app.config['ID_CARD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            id_card_image = filename
            print(f"✅ ID card saved: {filename}")
        except Exception as e:
            print(f"❌ Error saving ID card: {e}")
            id_card_image = None
    
    borrow_date = data.get('borrow_date', datetime.now().strftime('%Y-%m-%d'))
    return_date = data.get('return_date', (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
    total_borrow_price = calculate_borrow_price(borrow_date, return_date, settings, items)
    
    items_to_store = []
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        items_to_store.append({
            'name': book.title_ar if book else item.get('name'),
            'author': book.author_ar if book else item.get('author'),
            'quantity': item.get('quantity', 1),
            'price': book.price if book else item.get('price', 0)
        })
    
    new_borrow = BorrowOrder(
        member_name=data.get('name'),
        member_phone=data.get('phone'),
        member_email=data.get('email'),
        id_card_number=data.get('id_card_number'),
        id_card_image=id_card_image,
        books=json.dumps(items_to_store),
        borrow_date=borrow_date,
        return_date=return_date,
        total_borrow_price=total_borrow_price,
        status='pending'
    )
    db.session.add(new_borrow)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': translations[lang]['order_confirmed'], 
        'order_id': new_borrow.id,
        'invoice_url': f'/invoice/show/borrow/{new_borrow.id}'
    })

# ==================== طلب حضوري ====================

@app.route('/admin/in_person_order', methods=['POST'])
@login_required
def in_person_order():
    lang = session.get('lang', 'ar')
    data = request.get_json()
    settings = AdminSettings.get()
    
    session.pop('last_order_id', None)
    session.pop('current_invoice_id', None)
    
    order_type = data.get('order_type')
    customer_name = data.get('customer_name')
    customer_phone = data.get('customer_phone')
    customer_address = data.get('customer_address', 'حضوري بالمكتبة')
    items = data.get('items', [])
    
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            if item.get('quantity', 1) > book.quantity:
                return jsonify({'success': False, 'message': f'الكمية المطلوبة من كتاب "{book.get_title(lang)}" أكبر من المتاحة ({book.quantity})'})
    
    for item in items:
        book = Book.query.filter_by(title_ar=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_fr=item.get('name')).first()
        if not book:
            book = Book.query.filter_by(title_en=item.get('name')).first()
        if book:
            book.quantity -= item.get('quantity', 1)
    
    if order_type == 'purchase':
        total_price = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
        days = 0
        borrow_date = None
        return_date = None
    else:
        days = data.get('days', 1)
        total_books = sum(item.get('quantity', 1) for item in items)
        total_price = (days * settings.borrow_price_per_day) * total_books
        borrow_date = datetime.now().strftime('%Y-%m-%d')
        return_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    new_order = InPersonOrder(
        order_type=order_type,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        items=json.dumps(items),
        total_price=total_price,
        days=days,
        borrow_date=borrow_date,
        return_date=return_date,
        status='confirmed'
    )
    db.session.add(new_order)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': translations[lang]['order_confirmed'], 
        'order_id': new_order.id,
        'invoice_url': f'/invoice/show/in_person/{new_order.id}'
    })

# ==================== دوال الإجراءات (مع توجيه مباشر) ====================

@app.route('/admin/confirm_purchase/<int:id>')
@login_required
def confirm_purchase(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = PurchaseOrder.query.get_or_404(id)
    order.status = 'confirmed'
    db.session.commit()
    flash(translations[lang]['flash_order_confirmed'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/deliver_purchase/<int:id>')
@login_required
def deliver_purchase(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = PurchaseOrder.query.get_or_404(id)
    order.status = 'delivered'
    db.session.commit()
    flash(translations[lang]['flash_order_delivered'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/delete_purchase/<int:id>')
@login_required
def delete_purchase(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = PurchaseOrder.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    flash(translations[lang]['flash_order_deleted'], 'info')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/confirm_borrow/<int:id>')
@login_required
def confirm_borrow(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    borrow.status = 'confirmed'
    db.session.commit()
    flash(translations[lang]['flash_borrow_confirmed'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/return_borrow/<int:id>')
@login_required
def return_borrow(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    borrow.status = 'returned'
    db.session.commit()
    flash(translations[lang]['flash_borrow_returned'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/delete_borrow/<int:id>')
@login_required
def delete_borrow(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    if borrow.id_card_image:
        image_path = os.path.join(app.config['ID_CARD_FOLDER'], borrow.id_card_image)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(borrow)
    db.session.commit()
    flash(translations[lang]['flash_borrow_deleted'], 'info')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/edit_borrow_dates/<int:id>', methods=['POST'])
@login_required
def edit_borrow_dates(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    new_borrow_date = request.form.get('borrow_date')
    new_return_date = request.form.get('return_date')
    items = json.loads(borrow.books)
    
    if new_borrow_date:
        borrow.borrow_date = new_borrow_date
    if new_return_date:
        borrow.return_date = new_return_date
    
    borrow.total_borrow_price = calculate_borrow_price(borrow.borrow_date, borrow.return_date, settings, items)
    
    db.session.commit()
    flash(translations[lang]['flash_dates_updated'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/archive_purchase/<int:id>')
@login_required
def archive_purchase(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = PurchaseOrder.query.get_or_404(id)
    if order.status == 'pending':
        flash(translations[lang]['flash_cannot_archive_pending'], 'danger')
        return redirect(url_for('admin_panel', section=section))
    
    order.status = 'archived'
    order.archived_at = datetime.now()
    db.session.commit()
    flash(translations[lang]['flash_archived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/unarchive_purchase/<int:id>')
@login_required
def unarchive_purchase(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = PurchaseOrder.query.get_or_404(id)
    order.status = 'delivered'
    order.archived_at = None
    db.session.commit()
    flash(translations[lang]['flash_unarchived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/archive_borrow/<int:id>')
@login_required
def archive_borrow(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    if borrow.status == 'pending':
        flash(translations[lang]['flash_cannot_archive_borrow_pending'], 'danger')
        return redirect(url_for('admin_panel', section=section))
    
    borrow.status = 'archived'
    borrow.archived_at = datetime.now()
    db.session.commit()
    flash(translations[lang]['flash_archived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/unarchive_borrow/<int:id>')
@login_required
def unarchive_borrow(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    borrow = BorrowOrder.query.get_or_404(id)
    borrow.status = 'returned'
    borrow.archived_at = None
    db.session.commit()
    flash(translations[lang]['flash_unarchived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/archive_in_person/<int:id>')
@login_required
def archive_in_person(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = InPersonOrder.query.get_or_404(id)
    order.status = 'archived'
    order.archived_at = datetime.now()
    db.session.commit()
    flash(translations[lang]['flash_archived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/unarchive_in_person/<int:id>')
@login_required
def unarchive_in_person(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = InPersonOrder.query.get_or_404(id)
    order.status = 'confirmed'
    order.archived_at = None
    db.session.commit()
    flash(translations[lang]['flash_unarchived'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/delete_in_person/<int:id>')
@login_required
def delete_in_person(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = InPersonOrder.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    flash(translations[lang]['flash_in_person_deleted'], 'info')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/update_in_person/<int:id>', methods=['POST'])
@login_required
def update_in_person(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    order = InPersonOrder.query.get_or_404(id)
    settings = AdminSettings.get()
    
    order.customer_name = request.form.get('customer_name')
    order.customer_phone = request.form.get('customer_phone')
    order.customer_address = request.form.get('customer_address')
    
    if order.order_type == 'borrow':
        days = int(request.form.get('days', order.days))
        order.days = days
        order.borrow_date = datetime.now().strftime('%Y-%m-%d')
        order.return_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    items_json = request.form.get('items')
    if items_json:
        items = json.loads(items_json)
        order.items = json.dumps(items)
        
        if order.order_type == 'purchase':
            order.total_price = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
        else:
            total_books = sum(item.get('quantity', 1) for item in items)
            order.total_price = (order.days * settings.borrow_price_per_day) * total_books
    
    db.session.commit()
    flash(translations[lang]['flash_in_person_updated'], 'success')
    return redirect(url_for('admin_panel', section=section))

# ==================== إدارة الكتب ====================

@app.route('/admin/add_book', methods=['POST'])
@login_required
def add_book():
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'books')
    title_ar = request.form.get('title_ar')
    title_fr = request.form.get('title_fr')
    title_en = request.form.get('title_en')
    author_ar = request.form.get('author_ar')
    author_fr = request.form.get('author_fr')
    author_en = request.form.get('author_en')
    category = request.form.get('category')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity', 1))
    description_ar = request.form.get('description_ar', '')
    description_fr = request.form.get('description_fr', '')
    description_en = request.form.get('description_en', '')
    
    image = 'default.png'
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
            image = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image))
    
    new_book = Book(
        title_ar=title_ar, title_fr=title_fr, title_en=title_en,
        author_ar=author_ar, author_fr=author_fr, author_en=author_en,
        category=category, price=price, image=image, quantity=quantity,
        description_ar=description_ar, description_fr=description_fr, description_en=description_en,
        is_active=True
    )
    db.session.add(new_book)
    db.session.commit()
    flash(translations[lang]['flash_book_added'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/edit_book/<int:id>', methods=['POST'])
@login_required
def edit_book(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'books')
    book = Book.query.get_or_404(id)
    book.title_ar = request.form.get('title_ar')
    book.title_fr = request.form.get('title_fr')
    book.title_en = request.form.get('title_en')
    book.author_ar = request.form.get('author_ar')
    book.author_fr = request.form.get('author_fr')
    book.author_en = request.form.get('author_en')
    book.category = request.form.get('category')
    book.price = float(request.form.get('price'))
    book.quantity = int(request.form.get('quantity', 1))
    book.description_ar = request.form.get('description_ar', '')
    book.description_fr = request.form.get('description_fr', '')
    book.description_en = request.form.get('description_en', '')
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            if book.image and book.image != 'default.png':
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], book.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
            book.image = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], book.image))
    
    db.session.commit()
    flash(translations[lang]['flash_book_updated'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/delete_book/<int:id>')
@login_required
def delete_book(id):
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'books')
    book = Book.query.get_or_404(id)
    if book.image and book.image != 'default.png':
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], book.image)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(book)
    db.session.commit()
    flash(translations[lang]['flash_book_deleted'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/update_settings', methods=['POST'])
@login_required
def update_settings():
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'settings')
    settings = AdminSettings.get()
    settings.borrow_price_per_day = float(request.form.get('borrow_price_per_day', 20.0))
    settings.purchase_delivery_fee = float(request.form.get('purchase_delivery_fee', 30.0))
    settings.borrow_delivery_fee = float(request.form.get('borrow_delivery_fee', 20.0))
    settings.whatsapp_number = request.form.get('whatsapp_number', '0655882566')
    db.session.commit()
    flash(translations[lang]['flash_settings_updated'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/change_password', methods=['POST'])
@login_required
def change_password():
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'settings')
    settings = AdminSettings.get()
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if old_password != settings.password:
        flash(translations[lang]['flash_wrong_old_password'], 'danger')
        return redirect(url_for('admin_panel', section=section))
    
    if new_password != confirm_password:
        flash(translations[lang]['flash_password_mismatch'], 'danger')
        return redirect(url_for('admin_panel', section=section))
    
    if len(new_password) < 4:
        flash(translations[lang]['flash_password_too_short'], 'danger')
        return redirect(url_for('admin_panel', section=section))
    
    settings.password = new_password
    db.session.commit()
    flash(translations[lang]['flash_password_changed'], 'success')
    return redirect(url_for('admin_panel', section=section))

@app.route('/admin/id_card_image/<filename>')
@login_required
def id_card_image(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['ID_CARD_FOLDER'], filename)

# ==================== لوحة التحكم ====================

@app.route('/admin/login', methods=['POST'])
def admin_login():
    lang = session.get('lang', 'ar')
    password = request.form['password']
    settings = AdminSettings.get()
    if password == settings.password:
        session['admin_logged_in'] = True
        flash(translations[lang]['flash_login_success'], 'success')
        return redirect(url_for('admin_panel'))
    else:
        flash(translations[lang]['flash_wrong_password'], 'danger')
        return redirect(url_for('home'))

@app.route('/admin/logout')
def admin_logout():
    lang = session.get('lang', 'ar')
    session.pop('admin_logged_in', None)
    flash(translations[lang]['flash_logout_success'], 'info')
    return redirect(url_for('home'))

@app.route('/admin')
@login_required
def admin_panel():
    lang = session.get('lang', 'ar')
    section = request.args.get('section', 'all_orders')
    
    # 🔥 جلب الطلبات وترتيبها بحيث تظهر "pending" أولاً
    purchase_orders = sort_orders_by_status(PurchaseOrder.query.filter(PurchaseOrder.status != 'archived').all())
    borrow_orders = sort_orders_by_status(BorrowOrder.query.filter(BorrowOrder.status != 'archived').all())
    in_person_orders = sort_orders_by_status(InPersonOrder.query.filter(InPersonOrder.status != 'archived').order_by(InPersonOrder.created_at.desc()).all())
    
    archived_purchases = PurchaseOrder.query.filter_by(status='archived').all()
    archived_borrows = BorrowOrder.query.filter_by(status='archived').all()
    archived_in_person = InPersonOrder.query.filter_by(status='archived').all()
    
    settings = AdminSettings.get()
    
    total_revenue = db.session.query(db.func.sum(PurchaseOrder.total_price)).filter(PurchaseOrder.status == 'delivered').scalar() or 0
    total_revenue += db.session.query(db.func.sum(BorrowOrder.total_borrow_price)).filter(BorrowOrder.status == 'returned').scalar() or 0
    total_revenue += db.session.query(db.func.sum(InPersonOrder.total_price)).filter(InPersonOrder.status == 'confirmed').scalar() or 0
    
    pending_purchases = PurchaseOrder.query.filter_by(status='pending').count()
    pending_borrows = BorrowOrder.query.filter_by(status='pending').count()
    
    return render_template('admin_dashboard.html',
                         lang=lang, t=translations[lang],
                         books=Book.query.filter_by(is_active=True).all(),
                         purchase_orders=purchase_orders,
                         borrow_orders=borrow_orders,
                         in_person_orders=in_person_orders,
                         archived_purchases=archived_purchases,
                         archived_borrows=archived_borrows,
                         archived_in_person=archived_in_person,
                         total_revenue=total_revenue,
                         pending_purchases=pending_purchases,
                         pending_borrows=pending_borrows,
                         settings=settings,
                         section=section)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_books()
        AdminSettings.get()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    def init_app():
    with app.app_context():
        db.create_all()
        init_books()
        AdminSettings.get()

init_app()
