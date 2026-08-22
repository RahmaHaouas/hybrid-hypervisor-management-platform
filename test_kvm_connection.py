import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("KVM_HOST")
user = os.getenv("KVM_USER")
password = os.getenv("KVM_PASSWORD")

print(f"Connexion SSH à {host}...")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, password=password)

print("✅ Connexion SSH réussie !")

stdin, stdout, stderr = client.exec_command("virsh --connect qemu:///system list --all")
output = stdout.read().decode()
error = stderr.read().decode()

print("\n--- Résultat de 'virsh list --all' ---")
print(output)

if error:
    print("--- Erreurs ---")
    print(error)

client.close()
print("Déconnecté.")