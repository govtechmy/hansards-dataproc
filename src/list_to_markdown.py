# Adapted from: https://gist.github.com/m0neysha/219bad4b02d2008e0154
# and https://gist.github.com/OsKaR31415/955b166f4a286ed427f667cb21d57bfd

def make_markdown_table(array):
    nl = "\n"

    # get the width of each column
    widths = [max(len(line[i]) for line in array) for i in range(len(array[0]))]
    # make every width at least 3 colmuns, because the separator needs it
    widths = [max(w, 3) for w in widths]
    # center text according to the widths
    array = [[elt.center(w) for elt, w in zip(line, widths)] for line in array]
    markdown = ""

    for entry in array:
        markdown += f"| {' | '.join(entry)} |{nl}"

    return markdown
