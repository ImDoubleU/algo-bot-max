"""Compatibility entrypoint for the current three-pass training-material audit."""

from audit_training_materials import main


if __name__ == "__main__":
    print("Legacy command redirected to docs/audit_training_materials.py")
    main()
