from ecdsa import SigningKey, NIST256p

def gerar_chave(urna_id):
    sk = SigningKey.generate(curve=NIST256p)
    with open(f"{urna_id}_priv.pem", "wb") as f:
        f.write(sk.to_pem())

    vk = sk.get_verifying_key()
    with open(f"{urna_id}_pub.pem", "wb") as f:
        f.write(vk.to_pem())

# Gerar chave para URNA001
gerar_chave("urna001")
