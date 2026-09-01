"""Compatibility entrypoint for the measured video-series audit."""

from audit_video_series_strict import main


if __name__ == "__main__":
    print("Legacy command redirected to docs/audit_video_series_strict.py")
    main()
