from Crypto.PublicKey import RSA

from exchange.base.cryptography.rsa import RSASigner, RSAVerifier

PRIVATE_KEY_STR = '''-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDWXGA/XEEe0BLs
6+AohRA2Yk83W8EAroE0q89ZYunIlX5L+yXhi0Nmy02iAQG2u6IvRrT4WPKIBsLX
YXuJAReSFRQse5xYq9j7aiW8tZ56E1x12Wf5paZIT43xny1rQ2vDbom1uEpX1cyW
RzPNGl1FYpSJIT6wr9dOiCxwmaktdwL4LDqj1jxsjG05zZOrUUoJ78yvWgifKIDh
17gM2BSEewYrZI2CXGbUZqs/hflN8P4sDxuupjlEvaEP0EOJd6km33NtxqPdMito
78lPGbPtCIXPv4Y+DjjvW1O7zzDNRbqCpnTVv4zpuHpNKfH2Dj9U0uFnWutavRM0
qIDEo7XJAgMBAAECggEAEtzoH0s388UtlSmgfRBQf+igvedWEYBJoF/qDByXI+57
waXlDHbbxITpXPMnunPCbtSTAjOZi/zEUn2iiEjPUSyHrO5nsKnWmzEZBwUYX/eq
MDikXKSGAGD3xaZTMdgp+HWWqqX/7MDEkwjK9yZ1xLBLD9IcGSIwGRoEhxgOehCQ
kT+Yea9dyJhjZZNyYnHurDPjGg/JmWso144sJP2u7TUXoUprXTYdLb4oOuvJQrAR
hoFi0YgapBTp8+ecp/0SLhPXLS5uFUd+9fD9Il6oDM1QuwXOv8N+HdHy257TGuZG
44Rc1dH/lKTl1Eby4zIslmEwXVPjSZ7IvAEVUFZ3DQKBgQD/edD1Z4hvRRh8Rn9M
QoBELk8HGUbLQ3fxF2uGvkyi644UnNtG3kyH6/XiQjgfwLsEoW1xoU4GJPJLhDvG
3Lzo8D4OnmcPKNXa1TUXDq2QWiBCuU9ZNA2BeUh1mKV5nyX+EKxVVDUtQUAYYubz
2e0UFVXANibYmmoazLj3b4rPfwKBgQDWzPcBLCcd0DfK3W2e0bJ6HFMTLt9GAVJD
wy+zoUvV+BkTMBIxCgF4jMJgRNEEAyRMQouWesVCbkCGBxf9vFKabjTZBf27g8WN
0Qjos++Pgt23xneODSTPupwX0dqI+15haNJKBiRvbr3Jx/UrNEZ3cSCWOh1cxaXU
5yq9QCeetwKBgA2iyN5wWj3mKDpp4N2HJyV8e0dbuAWdYkeCAoE8owaHIBxFiwar
UtZmZ8dd1XUMam8C1r6b53g4fJ4/PpmMqqCcQhOxrLqIaXG2s5C5fdYYmWQ2U9/l
AVuJx65PKXXmYra+2RPs3LG/q9YhYUZeuWK7CMqrmUMyartnde/vCi+tAoGAV584
y2OleUXs3HZDN1w3QBS51sNyFO6JDlda6B3N/7S7FdawNQzt2K0ixX6M/OQDNJCY
vIPMX/L1ozbVlI3z7Ec0i6sj/BAe0GELD1IHUTWDGGp/bpTyBUMMVbMnQGW59GZ8
EfI7frFf/iXxXvRuIl8leeKvA58krJq4FodLIjUCgYAlCu8lUEZo/KWNrzAbd2Nt
Pni72IazxCWzxFmn33l6MvSDEkPKr1kVsZXMf5L1r+5eJSKombJpngvuenGUx711
hmhlHIaG5DDfLABZK/khMWku5Csg4x9sPU4P3MvyxYSre5BN35O4pDq6BMBIJUx3
NO/YNhzqm/gSHpYArTWJYg==
-----END PRIVATE KEY-----'''


PUBLIC_KEY_STR = '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1lxgP1xBHtAS7OvgKIUQ
NmJPN1vBAK6BNKvPWWLpyJV+S/sl4YtDZstNogEBtruiL0a0+FjyiAbC12F7iQEX
khUULHucWKvY+2olvLWeehNcddln+aWmSE+N8Z8ta0Nrw26JtbhKV9XMlkczzRpd
RWKUiSE+sK/XTogscJmpLXcC+Cw6o9Y8bIxtOc2Tq1FKCe/Mr1oInyiA4de4DNgU
hHsGK2SNglxm1GarP4X5TfD+LA8brqY5RL2hD9BDiXepJt9zbcaj3TIraO/JTxmz
7QiFz7+GPg4471tTu88wzUW6gqZ01b+M6bh6TSnx9g4/VNLhZ1rrWr0TNKiAxKO1
yQIDAQAB
-----END PUBLIC KEY-----'''


EXPECTED_SIGNATURE = '''UhOIQYpdm6XZRdIOYCVBNPZdybTSr88sR8jvAdfpiy8xD7pgXPZ+HilNb1zIGc+1eaSe2MEfPyMH
t9BZDqW0keVaX9vkl8YH2veJKRQIO0mtPstPxOMtXTZwqguhPc7USp5p82ExjRKKgM1/uGEDg5bP
gigSd9AyiQK55lhsXs23wVcguOGAw3ZUABSQqYujru3bLUXJ6PD19Z/vrmLzpQgrEdOraZ186gwM
nyzQrYExpNWlt/O63RW/KImPiuBj5tmYjy/bKdpHJzCqZPntcGqynSvPHEk0DloG7+mZJp6gnxTH
AN5InuB6mD9x5ruRSxoBpynMbGBCO8k4xjLigQ==
'''


def test_sign_and_verify():
    rsa_signer_1 = RSASigner(PRIVATE_KEY_STR)

    input = '357,09126012270,0370800001'
    signature = rsa_signer_1.sign(input)
    assert signature == EXPECTED_SIGNATURE

    verifier1 = RSAVerifier(PUBLIC_KEY_STR)
    assert verifier1.verify(input, signature) is True

    # Test invalid signature
    assert verifier1.verify(input + 'abc', signature) is False

    # Test verify with different public key
    keypair = RSA.generate(2048)
    public_key = keypair.public_key().export_key()
    verifier2 = RSAVerifier(public_key)
    assert verifier2.verify(input, signature) is False
