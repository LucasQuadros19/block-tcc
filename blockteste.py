from flask import Flask, request, jsonify
import hashlib
import json
from time import time
from ecdsa import SigningKey, VerifyingKey, NIST256p, BadSignatureError
import base64

app = Flask(__name__)

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_votos = []
        self.create_block(proof=1, previous_hash='0')

        self.urnas_autorizadas = {
            "URNA001": self.load_public_key("urna001_pub.pem"),
        }

        self.eleitores_votaram = set()

    def load_public_key(self, filename):
        with open(filename, "rb") as f:
            return VerifyingKey.from_pem(f.read())

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'votos': self.current_votos,
            'proof': proof,
            'previous_hash': previous_hash
        }
        self.current_votos = []
        self.chain.append(block)
        return block

    def get_previous_block(self):
        return self.chain[-1]

    def hash(self, block):
        encoded_block = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()

    def is_chain_valid(self):
        previous_block = self.chain[0]
        for i in range(1, len(self.chain)):
            block = self.chain[i]
            if block['previous_hash'] != self.hash(previous_block):
                return False
            previous_block = block
        return True

    def verify_signature(self, mensagem, assinatura_b64, chave_publica):
        try:
            assinatura = base64.b64decode(assinatura_b64)
            chave_publica.verify(assinatura, mensagem.encode())
            return True
        except BadSignatureError:
            return False

    def add_voto(self, id_eleitor, candidato, urna_id, assinatura):
        # Verifica se a urna é autorizada
        if urna_id not in self.urnas_autorizadas:
            return {'erro': 'Urna não autorizada'}, 403

        # Verifica se o eleitor já votou
        if id_eleitor in self.eleitores_votaram:
            return {'erro': 'Este eleitor já votou'}, 400

        # Verifica a assinatura digital da urna
        mensagem = f"{id_eleitor}:{candidato}:{urna_id}"
        chave_publica = self.urnas_autorizadas[urna_id]
        if not self.verify_signature(mensagem, assinatura, chave_publica):
            return {'erro': 'Assinatura inválida'}, 403

        voto = {
            'id_eleitor': id_eleitor,
            'candidato': candidato,
            'urna_id': urna_id
        }

        self.current_votos.append(voto)
        self.eleitores_votaram.add(id_eleitor)

        if len(self.current_votos) >= 5:
            previous_block = self.get_previous_block()
            previous_hash = self.hash(previous_block)
            self.create_block(proof=1, previous_hash=previous_hash)

        return {'mensagem': 'Voto registrado com sucesso'}, 201


blockchain = Blockchain()

# ---------------- ROTAS ---------------- #

@app.route('/votar', methods=['POST'])
def votar():
    data = request.get_json()

    id_eleitor = data.get('id_eleitor')
    candidato = data.get('candidato')
    urna_id = data.get('urna_id')
    assinatura = data.get('assinatura')

    if not id_eleitor or not candidato or not urna_id or not assinatura:
        return jsonify({'erro': 'Dados incompletos'}), 400

    resultado, status = blockchain.add_voto(id_eleitor, candidato, urna_id, assinatura)
    return jsonify(resultado), status

@app.route('/cadeia', methods=['GET'])
def cadeia():
    return jsonify({'chain': blockchain.chain, 'length': len(blockchain.chain)}), 200

@app.route('/validar', methods=['GET'])
def validar():
    valido = blockchain.is_chain_valid()
    return jsonify({'valida': valido}), 200

# ---------------- EXECUÇÃO ---------------- #

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
