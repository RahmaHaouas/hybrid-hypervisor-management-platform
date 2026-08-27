import os
import ssl
from dotenv import load_dotenv
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

load_dotenv()

host = os.getenv("ESXI_HOST")
user = os.getenv("ESXI_USER")
password = os.getenv("ESXI_PASSWORD")

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

print(f"Connexion à {host}...")
si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
print("Connexion réussie !")

content = si.RetrieveContent()
print(f"Nom de l'hôte ESXi : {content.about.fullName}")

# Lister les VMs
container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
vms = container.view

print(f"\n Nombre de VMs trouvées : {len(vms)}")
for vm in vms:
    print(f" - {vm.name} | État : {vm.runtime.powerState}")

Disconnect(si)
print("\n Déconnecté.")