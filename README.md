This project aims to digitalise the Malaysian Dewan Rakyat Hansards from the PDFs available at the [official Parliament website](https://www.parlimen.gov.my/hansard-dewan-rakyat.html).

## Usage
1. Install requirements `pip install -r requirements.txt`
2. Bulk process with `python3 batch_run.py` (check the file and uncomment the wanted processes as this is still in active development)

![](README_images/usage.png)

To be specific,
Run `parse_pdf.py` to get the four output files of plaintext, binary bold and italic files (as 0, 1, or whitespaces) and tables.json. Th parsing will only process the content from DOA onwards (ignores table of contents and MP attendance).

Run `pretabulation_processing.py` to insert tables and to remove header rows, and other processing.

Run `edit_hansards.py` to edit the hansards to fix known any errors to ease tabulation.

Run `tabulate_hansards.py` to tabulate the hansards into a CSV file.'

## Notes

- As of 14 July 2022, 17 November 2021 (14-04-02-15) has the last _Penyata Rasmi_; the statements after all have the status _Naskhah belum disemak_
- Common (but not exhaustive) categories encountered are, in their order of appearance in _KANDUNGAN_
  - JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN
  - JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN,
  - RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT,
  - USUL-USUL,
  - RANG UNDANG-UNDANG
- The following fonts are found in the Hansard documents
  - '/Arial-BoldItalicMT',
  - '/Arial-BoldMT',
  - '/Arial-ItalicMT',
  - '/ArialMT',
  - '/TimesNewRomanPSMT'
- When parsing _JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN_ or _JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN_, an MP will start without ":", but the subsequent dialogue has ":". For example
> 1. Datuk Robert Lawson Chuat [Betong] minta Menteri Perdagangan Dalam... 
> 
> Menteri Perdagangan Dalam Negeri dan Hal Ehwal Pengguna [Dato Sri Alexander Nanta Linggi]: Terima kasih Tuan Yang di-Pertua dan..
> 
> Tuan Yang di-Pertua: Terima kasih. Soalan tambahan pertama.
- `14-04-2-15` shows that a subtopic change can happen and acknowledged in formatting mid-dialogue.
- Speakers usually have [] to give context of who they are representing (either representing their constituency or a ministry). Sometimes the speaker will not have [] further down in the discussion if they already appeared before with []. The Tuan Yang di-Pertua doesn't have [].
- The parser can detect boldness and italics accurately, but it cannot detect underlines nor give information on text sizes. To some extent, it will detect newlines and replace it with double spaces.
- Timestamps are removed as it is hard to extract them and place them correctly in the table, as they can occur out and in of the dialogue.
- Sometimes title from table of contents (TOC) have slight difference from in-text. In that case, use the in-text version.
- Why we don't parse subtopic from TOC: subtopic does not show up in TOC for _RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT_
- The DR.dd.mm.yyyy is not consistent: the dd can be zero-padded or not.
- TOC will say "USUL-USUL" but in-text the title is usually "USUL"
- Sometimes, USUL will somehow go under RANG UNDANG-UNDANG, ans some categories will go before others, ignoring the TOC order.
- We cannot make any useful parsing using font sizes.
- The current way of creating bold and italics files makes it convenient to check using a simple text editor and line numbers.
- Parsing 2018 gives 3 pages per second, giving around 1 minute per Hansard.
- extract_text has different layout than using page.chars, the latter does not retain most whitespaces, and use different text flow (see second page "Diterbitkan...", page.chars will put it at the top of the page even though it is at the bottom).
- We get the formatting using extract_words(extra_attrs=['fontname']). This will also segment words based on homogeneity of fontnames.

# On header rows
- Most Hansards start with the page number 1 in the same page of DOA except 14.3.2018, which starts with 11.
- 29.11.2018 when parsed displays the page numbers as 1  1 instead of 11
- 12.11.2019 displays as 12.11.201
- We decide to remove them in pretabulation as it can jut between important chunks as in DR. 22.5.2023 page 108.

# On parsing Table of Contents
- 17072018 does not bold its categories.

# Notes
- level-2 can have multilines, but level-1 must be on one single line. Example
- We only parse an annotation as its own without an author when it does not have any bold. This is because sometimes [Bangun] goes on a new line just because the author name is long e.g. 27032018 pg 29
- Sometimes Tepuk can be missing a [ e.g. Tepuk] at 18052020.

# Common annotations
- _Tepuk_
- _Ketawa_
- _Dewan ketawa_
- _Dewan riuh_
- _Pembesar suara dimatikan_

# Cautionary notes
- Be careful when berbelah bahagi shows up. Some Hansards present it differently than others. Usually, it will have the keywords hadir, bersetuju, and undi, and are usually bolded and lowercased, except for 17072019 where it is uppercased and hence parsed as a level_2.
- 30112020 and 23032022