esc = '\x1b'

reset  = f'{esc}[0m'
bold   = f'{esc}[1m'
debold = f'{esc}[25m'
fg_off = f'{esc}[39m'
bg_off = f'{esc}[49m'

fg = {
    'black':   f'{esc}[30m',
    'red':     f'{esc}[31m',
    'green':   f'{esc}[32m',
    'yellow':  f'{esc}[33m',
    'blue':    f'{esc}[34m',
    'magenta': f'{esc}[35m',
    'cyan':    f'{esc}[36m',
    'white':   f'{esc}[37m'
}

bg = {
    'black':   f'{esc}[40m',
    'red':     f'{esc}[41m',
    'green':   f'{esc}[42m',
    'yellow':  f'{esc}[43m',
    'blue':    f'{esc}[44m',
    'magenta': f'{esc}[45m',
    'cyan':    f'{esc}[46m',
    'white':   f'{esc}[47m'
}
