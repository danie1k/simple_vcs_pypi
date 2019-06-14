INDEX = '''
<!doctype html>
<html>
    <head>
        <title>Simple index</title>
        <style>
        html, body, a { margin: 0; padding: 0; border: 0; font-size: 100%%; font: inherit; vertical-align: baseline; }
        body { line-height: 1; margin: .5rem}
        a { display: block; padding: .5rem 1rem; border: 1px solid #ccc; margin: .5rem; }
        a:hover { background: #eee; }
        </style>
    </head>
    <body>
        %(links)s
    </body>
</html>
'''

REPOSITORY = '''
<!doctype html>
<html>
    <head>
        <title>%(repository_name)s</title>
        <style>
        html, body, a { margin: 0; padding: 0; border: 0; font-size: 100%%; font: inherit; vertical-align: baseline; }
        body { line-height: 1; margin: .5rem}
        a { display: block; padding: .5rem 1rem; border: 1px solid #ccc; margin: .5rem; }
        a:hover { background: #eee; }
        </style>
    </head>
    <body>
        %(links)s
    </body>
</html>
'''
