from cryptography.fernet import Fernet

# Generate a key
key = Fernet.generate_key()
print(key)
# Store this key securely! You will use it to create a Fernet instance later.
