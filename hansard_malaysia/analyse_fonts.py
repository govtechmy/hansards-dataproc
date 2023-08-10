import PyPDF2
from PyPDF2 import PdfFileReader
from pprint import pprint

"""
Results:
Font List
['/Arial-BoldItalicMT',
 '/Arial-BoldMT',–
 '/Arial-ItalicMT',
 '/ArialMT',
 '/TimesNewRomanPSMT']

Unembedded Fonts
{'/Arial-BoldItalicMT',
 '/Arial-BoldMT',
 '/Arial-ItalicMT',
 '/ArialMT',
 '/TimesNewRomanPSMT'}
"""


'''
01032023
Font List
['/Arial-BoldItalicMT',
 '/Arial-BoldMT',
 '/Arial-ItalicMT',
 '/ArialMT',
 '/BCDEEE+Calibri',
 '/TimesNewRomanPS-BoldMT',
 '/TimesNewRomanPSMT']

Unembedded Fonts
{'/Arial-BoldItalicMT',
 '/Arial-BoldMT',
 '/Arial-ItalicMT',
 '/ArialMT',
 '/TimesNewRomanPS-BoldMT',
 '/TimesNewRomanPSMT'}

'''

'''
DR-01112021
Font List
['/Arial-BoldItalicMT',
 '/Arial-BoldMT',
 '/Arial-ItalicMT',
 '/ArialMT',
 '/TimesNewRomanPSMT']

Unembedded Fonts
{'/Arial-BoldItalicMT',
 '/Arial-BoldMT',
 '/Arial-ItalicMT',
 '/ArialMT',
 '/TimesNewRomanPSMT'}
 '''

def walk(obj, fnt, emb):
    """
    If there is a key called 'BaseFont', that is a font that is used in the document.
    If there is a key called 'FontName' and another key in the same dictionary object
    that is called 'FontFilex' (where x is null, 2, or 3), then that fontname is 
    embedded.

    We create and add to two sets, fnt = fonts used and emb = fonts embedded.
    """
    if not hasattr(obj, 'keys'):
        return None, None
    fontkeys = {'/FontFile', '/FontFile2', '/FontFile3'}
    if '/BaseFont' in obj:
        fnt.add(obj['/BaseFont'])
    if '/FontName' in obj:
        if [x for x in fontkeys if x in obj]:  # test to see if there is FontFile
            emb.add(obj['/FontName'])

    for k in obj.keys():
        walk(obj[k], fnt, emb)

    return fnt, emb  # return the sets for each page


if __name__ == '__main__':
    fname = 'src_hansard/2021/DR-01112021.pdf'
    pdf = PdfFileReader(fname)
    fonts = set()
    embedded = set()
    for page in pdf.pages:
        obj = page.get_object()
        print("New object")
        print(obj)
        # updated via this answer:
        # https://stackoverflow.com/questions/60876103/use-pypdf2-to-detect-non-embedded-fonts-in-pdf-file-generated-by-google-docs/60895334#60895334 
        # in order to handle lists inside objects. Thanks misingnoglic !
        # untested code since I don't have such a PDF to play with.
        if type(obj) == PyPDF2.generic.ArrayObject:  # You can also do ducktyping here
            print("object is generic array object. Begin enumeration")
            for i in obj:
                if hasattr(i, 'keys'):
                    f, e = walk(i, fonts, embedded)
                    print(f)
                    print(e)
                    fonts = fonts.union(f)
                    embedded = embedded.union(e)
        else:
            print("object is not generic array object.")
            f, e = walk(obj['/Resources'], fonts, embedded)
            print(f)
            print(e)
            fonts = fonts.union(f)
            embedded = embedded.union(e)

    unembedded = fonts - embedded
    print('Font List')
    pprint(sorted(list(fonts)))
    if unembedded:
        print('\nUnembedded Fonts')
        pprint(unembedded)
    
    
    # print example text for each font type
    for font in fonts:
        print(font)
        for page in pdf.pages:
            obj = page.get_object()
            if type(obj) == PyPDF2.generic.ArrayObject:
                for i in obj:
                    if hasattr(i, 'keys'):
                        f, e = walk(i, fonts, embedded)
                        if font in f:
                            print(i)