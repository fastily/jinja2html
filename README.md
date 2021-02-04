# jinja2html
[![Python 3.8+](https://upload.wikimedia.org/wikipedia/commons/9/92/Blue_Python_3.8%2B_Shield_Badge.svg)](https://www.python.org)
[![License: GPL v3](https://upload.wikimedia.org/wikipedia/commons/8/86/GPL_v3_Blue_Badge.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)

jinja2html takes your jinja2 templates and outputs HTML.

More importantly, it supports developer-friendly live reloading so that you can create that masterpiece of a static website without ripping your hair out.

### Why jinja2html?

Blogging frameworks are a *dime a dozen*.  But what if you don't want to write a blog?  What if you wanted to make a static landing page, but without all that client-heavy nonsense like React/Vue/Angular/etc?  

That's where jinja2html comes in.

No fancy bells and whistles, no bull$hit, just your bold artisitic vision + jinja2html.

## Install
```bash
pip install jinja2html
```

This installs the CLI command, `jinja2html`, which can be used to generate html or start the local development server.

## Usage
```
usage: jinja2html.py [-h] [--generate] [--ignore IGNORE [IGNORE ...]] [--port PORT]

Developer friendly rendering of jinja2 templates.

optional arguments:
  -h, --help            show this help message and exit
  --generate            render all jinja2 files in the current directory, no livereload
  --ignore IGNORE [IGNORE ...]
                        folders to ignore
  --port PORT           serve website on this port
```

#### Examples
```bash
# run in dev mode, in the current directory
jinja2html

# generate html files for use in prod
jinja2html --generate

# generate html files for use in prod and ignore folders Foo/ and Bar/
jinja2html --generate --ignore Foo/ Bar/

# run in dev mode, on port 8080 and ignore folder hello/world/
jinja2html --port 8080 --ignore hello/world/
```

## Scope
jinja2html is designed for small and simple static websites.  If you're trying to do something big and complex, then you should stick with the tooling of a conventional front-end framework.