from src.clean import clean_contacts

def test_clean_basic():
    input_csv = 'name,email\nAlice, ALICE@TEST.COM \n'
    output = clean_contacts(input_csv)
    assert 'alice@test.com' in output
