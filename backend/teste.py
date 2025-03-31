import bcrypt
print(bcrypt.hashpw(b"teste", bcrypt.gensalt()))
