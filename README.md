# WebUntis-Fetcher

This project is modeled after the web application (by reverse engineering) and does
**not** use a publicly documented and stable API. So it can break at any time - 
whenever Untis decides to change their backend.

## TODO

- cancellations
- changes in teacher, subject or room

## Getting Started

1. Checkout this project to your computer (or just copy `main.py` and `config-template.ini`).
2. Copy `config-template.ini` to `config.ini` and edit it so it contains your data.
   - The section names (inside the `[]`) are used as titles for the time tables.
   - The `server` field has to be set to whatever your school uses. You can see the server
     name in the browser address bar when you are logged in, it's everything up to the first `/`. 
   - The `school` field has to contain whatever Untis calls the school. You can look it up
     by logging into your WebUntis account in a web browser and click the RSS icon on the
     "Today" page (small, orange). The link you're directed to contains the right name
     (look at the address bar of the browser).
   - The `class` field is not used to access the backend, but setting it (to any value)
     switches to "student" mode. If `class` is unset, the "teacher" mode is used, and class
     names are displayed next to the period subjects.
   - `firstname` and `lastname` are used to look up the person for which the time table should
     be displayed. This way you can use a parent login (which potentially has access to multiple
     children's time tables) and still determine what should be displayed.
3. Make sure that at least Python 3.9 and the necessary libraries are installed
   (e.g. by executing `pip3 install -r requirements.txt`). You can also set up a
   [venv](https://docs.python.org/3/library/venv.html) and install the requirements
   inside it (recommended).
4. Run `main.py` periodically, which will write the output to `output.html` in the same
   directory as the script - or provide a target filename as argument to the script.
