import os
import winrm
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("HYPERV_HOST")
user = os.getenv("HYPERV_USER")
password = os.getenv("HYPERV_PASSWORD")

print(f"Connexion WinRM à {host}...")

session = winrm.Session(host, auth=(user, password), transport="ntlm")
result = session.run_ps("Get-VM | Select-Object Name, State")

print("✅ Connexion réussie !")
print("\n--- Résultat de 'Get-VM' ---")
print(result.std_out.decode())

if result.std_err:
    print("--- Erreurs ---")
    print(result.std_err.decode(errors="ignore"))