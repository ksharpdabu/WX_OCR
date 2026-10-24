import sys

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from wxocr.selftest import run
        sys.exit(run(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--benchmark":
        from wxocr.benchmark import run
        sys.exit(run(sys.argv[2]))
    from wxocr.app import main
    main()
