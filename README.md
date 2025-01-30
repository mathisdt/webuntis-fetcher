# WebUntis-Fetcher

This project is modeled after the web application (by reverse engineering) and does
**not** use a publicly documented and stable API. So it can break at any time - 
whenever Untis decides to change their backend.

## Getting Started

### Installation

1. Clone [this project](https://github.com/mathisdt/webuntis-fetcher.git) to your computer,
   or download the repository content as
   [ZIP file](https://github.com/mathisdt/webuntis-fetcher/archive/refs/heads/master.zip). 
2. Make sure that at least Python 3.9 is installed.
3. Optionally can now set up a [venv](https://docs.python.org/3/library/venv.html) and install
   everything inside it (recommended). For creating it, execute `python3 -m venv venv`, and
   afterwards activate it by executing `source venv/bin/activate`. 
   The following steps stay the same, you just have to remember to activate the venv before 
   using webuntis-fetcher later.
4. Install the package including its dependencies. If you want to be able to do a `git pull`
   later and not have to re-install it, execute `pip3 install -e .`.
   If you don't care about that possibility, use `pip3 install .`.
5. Test your installation by executing `webuntis-fetcher`. An error message should be written
   to stderr pointing out that no mode was selected.

### Fetch Timetable

To configure the mode "timetable", copy 
[config-template.ini](https://raw.githubusercontent.com/mathisdt/webuntis-fetcher/refs/heads/master/config-template.ini)
to e.g. `config.ini` and edit it so it contains your data.

The section names (inside the `[]`) are used as titles for the time tables,
with the exception of `[OUTPUT]` which can contain `timetable_file` - this defines the target
location of the generated timetable. Each other section can contain the following entries.

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
- `teacher_fullname_function` can be set to the name of a function which returns a dict
  and is called only once per run - the result is used to result teacher names to
  their full names because sometimes the "names" in Webuntis are only abbreviations.
  For an example, see `kks_kannover_teachers` in the code.
- `statistics_file` can optionally point to a writable location of a XLSX file. Is does not 
  have to exist yet but it will be created if given. The content of this file will be
  preserved over the weeks, and new data will be appended on the first sheet. The overall
  statistics on the second sheet will be updated accordingly.

Now you can run `webuntis-fetcher timetable` periodically, which will write the output to
stdout - or provide a target filename via the config file. Any log messages will go to
stderr. Remember to activate the venv before (if you used one while installing).
You also can add another argument pointing to the location of your config file
if it's not `config.ini` in your current working directory.

### Fetch Messages

To configure the mode "messages", copy 
[config-template.ini](https://raw.githubusercontent.com/mathisdt/webuntis-fetcher/refs/heads/master/config-template.ini)
to e.g. `config.ini` and edit it so it contains your data.

The section names (inside the `[]`) are used as titles for the time tables,
with the exception of `[OUTPUT]` which is irrelevant here. As we're fetching messages,
it would make sense to include every login only once, even if if is used for muliple students.

- The `server` field has to be set to whatever your school uses. You can see the server
  name in the browser address bar when you are logged in, it's everything up to the first `/`. 
- The `school` field has to contain whatever Untis calls the school. You can look it up
  by logging into your WebUntis account in a web browser and click the RSS icon on the
  "Today" page (small, orange). The link you're directed to contains the right name
  (look at the address bar of the browser).
- `message_id_file` should point to any writable file name. It does not have
  to exist. In this file the IDs of handled messages are stored so you are not notified
  multiple times for the same message.
- `mail_from`, `mail_to` and `mail_host` are self-explanatory. `mail_to` can contain
  multiple addresses separated by a comma.

Now you can run `webuntis-fetcher messages` periodically, which will will send emails as
configured. Any log messages will go to stderr. Remember to activate the venv before
(if you used one while installing). You also can add another argument pointing to the
location of your config file if it's not `config.ini` in your current working directory.
