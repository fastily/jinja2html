"""main entry point for jinja2html"""
import argparse
import glob
from pathlib import Path

from bs4 import BeautifulSoup
import livereload
import jinja2


t_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."), autoescape=True)


def build(path, dev=True):
    """Builds the jinja template at the specified path

    Arguments:
        path {str} -- path to the jinja file to build as html

    Keyword Arguments:
        dev {bool} -- set True to enable development mode (injection of livereload js) (default: {True})
    """

    output = t_env.get_template(path).render()
    if dev:
        soup = BeautifulSoup(output, "lxml")
        body_tag = soup.find("body")

        # add config for liveReload
        script_tag = soup.new_tag("script")
        script_tag.string = 'window.LiveReloadOptions = {host: "localhost"}'
        body_tag.append(script_tag)

        # actually add the script
        body_tag.append(soup.new_tag("script", src="https://cdn.jsdelivr.net/npm/livereload-js@3.2.1/dist/livereload.min.js",
                                     integrity="sha256-Tm7IcDz9uE2N6RbJ0yeZiLbQRSrtMMMhWEFyG5QD8DI=", crossorigin="anonymous"))
        output = soup.prettify()

    with open(f"out/{path}", "w") as f:
        f.write(output)


def main():
    cli_parser = argparse.ArgumentParser(description="Renders jinja2 templates as html")
    cli_parser.add_argument("--generate", action='store_true', help="cause all jinja2 files in this directory to be rendered for prod")
    args = cli_parser.parse_args()

    all_templates = glob.glob("*.html")

    if(args.generate):
        for f in all_templates:
            build(f, False)
        return

    # setup dev folders
    Path("out").mkdir(parents=True, exist_ok=True)
    Path("templates").mkdir(parents=True, exist_ok=True)

    # server stuff
    server = livereload.Server()

    for p in glob.glob("*.html"):
        # build_func = jinja_to_html_for(p)
        def build_func(): return build(p)
        build_func()
        server.watch(p, build_func, 'forever')

    server.serve(root='out', open_url_delay=1)


if __name__ == '__main__':
    main()
