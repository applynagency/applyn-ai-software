EXECUTOR_VERSION = "1.0.0"

EXECUTION_STEPS = [
    ("npm install", "install"),
    ("npm run lint", "lint"),
    ("npm run type-check", "typecheck"),
    ("npm run build", "build"),
    ("npm test", "test"),
]
