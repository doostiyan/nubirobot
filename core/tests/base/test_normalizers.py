import pytest

from exchange.base.normalizers import normalize_digits, normalize_mobile, compare_names, compare_full_names, \
    normalize_name


@pytest.mark.unit
def test_normalize_digits():
    assert normalize_digits('۰۱۲۳۴۵۶۷۸۹') == '0123456789'
    assert normalize_digits('00۰۰00') == '000000'
    assert normalize_digits('+98۹۱۳۱۲۵۶۹۷۸') == '+989131256978'
    assert normalize_digits('۰۹۱۵۱۰۵۱۲۷۵') == '09151051275'


@pytest.mark.unit
def test_normalize_mobile():
    assert normalize_mobile('+989151002385') == '09151002385'
    assert normalize_mobile('989151002385') == '09151002385'
    assert normalize_mobile('9151002385') == '09151002385'
    assert normalize_mobile('۹۱۵۱۰۰۲۳۸۵') == '09151002385'
    assert normalize_mobile('009151002385') == '09151002385'


@pytest.mark.unit
def test_normalize_name():
    assert normalize_name(' امیرعلی ') == 'امیرعلی'
    assert normalize_name('اكبري') == 'اکبری'
    assert normalize_name('إسحـــــــــــاق') == 'اسحاق'
    assert normalize_name('خداٸی') == 'خدائی'
    assert normalize_name('امیر\nعلی') == 'امیر علی'
    assert normalize_name('محمد جواد') == 'محمد جواد'
    assert normalize_name('ملأزاده') == 'ملأزاده'
    assert normalize_name('رحمت الله') == 'رحمت الله'
    assert normalize_name('رحمت اله') == 'رحمت اله'
    assert normalize_name('پوری‌زاده') == 'پوری‌زاده'


@pytest.mark.unit
def test_compare_names():
    assert compare_names('امیرعلی', 'اکبری', 'امير علي', 'اكبري')
    assert not compare_names('امیرعلی', 'اکبری', 'امير', 'علی اکبری')
    assert not compare_names('امیرعلی', 'اکبری', 'اکبری', 'امیرعلی')
    assert not compare_names('امیرعلی', 'اکبری', 'امير', 'اکبری')
    assert not compare_names('امیرعلی', 'اکبری', 'علی', 'اکبری')
    assert compare_names('نرگس', 'ملائی', 'نرگس', 'ملاٸي')
    assert not compare_names('مجید', 'قلندری', 'قلندری', 'مجید')
    assert not compare_names('سید حسین', 'شمس موحد', 'حسین', 'شمس موحد')
    assert not compare_names('امید', 'خواجوئی نژاد', 'امید', 'خاجوئی نژ اد')
    assert compare_names('زهراء', 'حاجت پور بیرگانی', 'زهرا', 'حاجت پور بيرگاني')
    assert not compare_names('نسیم', 'روئین فرد', 'نسیم', 'روٸيني فرد')
    assert compare_names('جعفر', 'پنجهءانبوهی', 'جعفر', 'پنجهئانبوهی')
    assert compare_names('احد', 'بناءخطیبی', 'احد', 'بنائخطیبی')
    assert compare_names('جعفر', 'زهرائپور', 'جعفر', 'زهراء پور')
    assert compare_names('جعفر', 'زهراپور', 'جعفر', 'زهراء پور')
    assert compare_names('رمضان علی', 'جهانی', 'رمضانعلی', 'جهانی')
    assert compare_names('زلیخا', 'جعفری فتح', 'زليخا', 'جعفري فتــــــــح')
    assert compare_names('حسن', 'مؤیدی', 'حسن', 'م؟یدی')
    assert not compare_names('حسن', 'مؤیدی', 'حسن', 'ما؟دی')
    assert compare_names('مريم', 'شاه پسندي', ' مریم', 'شاه پسندی')


@pytest.mark.unit
def test_compare_full_names():
    assert compare_full_names('امیرعلی اکبری', 'امير علي اكبري')
    assert not compare_full_names('امیرعلی اکبری', 'اکبری امیرعلی')
    assert not compare_full_names('حمید علوی', 'حمیده علوی')
    assert not compare_full_names('حسین نورزاد', 'حسین نورزادی')
    assert not compare_full_names('نوژان قیاسی', 'نویان قیاسی')
    assert compare_full_names('امیرعلی اکبری', 'امیر علی‌اکبری')
    assert compare_full_names('رؤیا مؤمنی', 'رویا مومنی')
    assert compare_full_names('نادر آقایی', 'نادر اقاٸي')
    assert compare_full_names('رحمت الله اتوکش', 'رحمت اله اتوکش')
    assert not compare_full_names('فرید رحمت اللهی', 'فرید رحمت الهی')
    assert compare_full_names('سبأ نرگسی', 'سبا نرگسی')
    assert not compare_full_names('امیر رنجبر', 'امیر پوررنجبر')
    assert compare_full_names('رؤیا رهائی فرد', 'رویا رهائی فرد')
    assert compare_full_names('سعیدرضا نبیئی', 'سعیدرضا نبییی')
    assert not compare_full_names('ویدا آزادیخواه', 'ویدا آزادیخواه ٣١٤ ٣١٦٢٠٤٧ ١')
    assert compare_full_names('ایرج ترکاون نژاد نقده', 'ايرج تركاون\xa0نژادنقده')
    assert compare_full_names('محمد اسدالله زاده اندواری', 'محمد اسداله زاده اندواری')
    assert compare_full_names('محمد حسین مؤمنی', 'محمدحسین م٠منی')
