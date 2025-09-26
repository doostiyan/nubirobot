def test_version_api(client):
    response = client.post('/check/version')
    assert response.status_code == 200
    assert 'version' in response.json
    for key in ("api", "web", "android"):
        assert key in response.json['version']


def test_debug_api(client):
    response = client.get('/check/debug')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert '-' in response.json['version']
