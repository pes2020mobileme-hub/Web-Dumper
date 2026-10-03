# Web Dumper 🌐📥

A Python script to download a single web page, including its HTML, CSS, JavaScript, and images, and save it for offline browsing.

## Features ✨

- Download the HTML, CSS, JavaScript, and image files referenced by one page.
- Mirror the site's directory structure locally, so assets with the same file name never collide.
- Skip assets that cannot be fetched (missing, blocked, inline `data:` URIs) and report each one on stderr instead of aborting the run.
- Display a simple animated message during the download process.

## Requirements 📋

- Python 3.10 or newer (CI covers 3.10 – 3.13)
- `requests` library
- `beautifulsoup4` library

Install the required libraries using pip:

```bash
pip install -r requirements.txt
```

## How to Use 🚀

1. **Clone the repository**:

    ```bash
    git clone https://github.com/hu5o-dev/Web-Dumper.git
    cd Web-Dumper
    ```

2. **Run the script**:

    On Windows, double-click `run.bat` — it locates Python for you (`py -3`, falling back to `python`) and starts the script:

    ```bat
    run.bat
    ```

    Anywhere else, or if you already have a Python environment set up:

    ```bash
    python WebDumper.py
    ```

    `run.bat` always runs the script from its own folder, so the download folder is created next to it.

3. **Enter the URL** when prompted. `https://` is added automatically if you leave it out, and `localhost` / `127.0.0.1` default to `http://`. The page is saved to a folder named after the website's hostname.

## Example 🖥️

```bash
Enter the URL of the website to download: https://example.com
```

The page is downloaded into a folder named `example.com_download`.

## How It Works 🔍

- The script first creates a local directory to store the downloaded files.
- It downloads the main HTML file and saves it as `index.html`.
- It parses the HTML to find stylesheets (`<link rel="stylesheet">`), scripts (`<script src>`), and images (`<img src>`).
- Each asset keeps its original directory structure inside the output folder, so `/css/app.css` becomes `css/app.css` and two files named `logo.png` in different folders do not overwrite each other.
- Each asset is downloaded with a timeout; assets that fail or use an unsupported URL are reported on stderr and left pointing at their original remote URL.
- The script updates the HTML file to use local paths for the assets it downloaded.
- An animated "Downloading..." message is displayed during the process.

## Notes 📝

- This script is intended for educational purposes and personal use.
- Be mindful of the website’s `robots.txt` file and usage policies before downloading content.

## License 📜

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing 🤝

Feel free to submit issues or pull requests if you have suggestions or improvements. 

## Contact 📧

If you have any questions, please reach out to [hugo@hugo.city](mailto:hugo@hugo.city).

---

Happy coding! 🚀
