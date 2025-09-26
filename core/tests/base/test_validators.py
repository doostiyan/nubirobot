import pytest

from exchange.base.validators import validate_email, validate_national_code, validate_iban, validate_name


@pytest.mark.unit
def test_validate_email():
    assert validate_email('amiraliakbari@gmail.com')
    assert not validate_email('amiraliakbari@gmil.com')


@pytest.mark.unit
def test_validate_national_code():
    assert validate_national_code('0921456441')
    assert not validate_national_code('0921456442')
    assert not validate_national_code('092145644')
    assert validate_national_code('5260194896')
    assert not validate_national_code('۵۲۶۰۱۹۴۸۹۶')


@pytest.mark.unit
def test_validate_iban():
    assert validate_iban('IR910540082280001252435001')
    assert validate_iban('IR910540082280000173435002')
    assert not validate_iban('IR91054008228000017343502')
    assert not validate_iban('IR9105400822800001734350021')
    assert not validate_iban('I0910540082280000173435002')


@pytest.mark.unit
def test_validate_name():
    assert validate_name('امیرعلی')
    assert validate_name(' امیرعلی')
    assert validate_name('اکبری')
    assert validate_name('بنی‌فاطمه')
    assert validate_name('طه')
    assert not validate_name('ق')
    assert not validate_name(' ق ')
    assert validate_name('رحمت الله')
    assert validate_name('رؤیا')
    assert validate_name('سبأ')
    assert validate_name('رهائی فرد')
    assert not validate_name('علی 2')
    assert not validate_name('Ali')
    assert not validate_name('Amir علی')
    assert not validate_name('امیر\nعلی')
    assert not validate_name('امیر\tعلی')
