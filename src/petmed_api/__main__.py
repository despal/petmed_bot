"""uvicorn petmed_api.app:app --reload --host 127.0.0.1 --port 8000"""

import uvicorn


def main() -> None:
    uvicorn.run("petmed_api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
