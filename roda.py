import os
import subprocess

def run_commands():
    print("🔧 Limpando diretórios e arquivos antigos...")
    os.system("rm -rf data")
    os.system("rm -f config.py")

    print("🚀 Executando script.py...")
    subprocess.run(["python", "script.py"], check=True)

    print("🌐 Iniciando main.py na porta 5001...")
    subprocess.run(["python", "main.py", "5001"], check=True)

if __name__ == "__main__":
    try:
        run_commands()
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar comando: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Execução interrompida pelo usuário.")
