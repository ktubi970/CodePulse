from src.clean import clean_contacts

def test_verif_clean():
    input_csv = 'name,email\nAlice, A@B.COM\nBob, invalid\nAlice, a@b.com\n'
    output = clean_contacts(input_csv)
    lines = [l.strip() for l in output.strip().splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[0] == 'name,email'
    assert lines[1] == 'Alice,a@b.com'
