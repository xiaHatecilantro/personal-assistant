import os


os.environ["DATABASE_URL"] = "sqlite:///./test_auth_scoping.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
