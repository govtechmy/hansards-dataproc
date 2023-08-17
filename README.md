This project aims to digitalise the Malaysian Dewan Rakyat Hansards from the PDFs available at the [official Parliament website](https://www.parlimen.gov.my/hansard-dewan-rakyat.html).

## Usage
1. Install requirements `pip install -r requirements.txt`
2. `cd hansard_malaysia`
3. Bulk process with `python3 main.py`

If the program terminates in the later stage due to uncaught errors (unlikely), you can rerun the program and skip downloading files and adding markup with `-skipdownload` and `-skipmarkup` respectively.

### To run a specific session
1. Make sure the Hansards PDF are already downloaded. If not, run `download_hansard.py` to download all session files into `src_hansard`. You can also specify the start date.
2. Run `python3 generate_markup.py XX-XX-XX-XX`, where XX-XX-XX-XX is the session code (eg. 14-04-01-16). This will add markup tags to bold and italic text, output as a folder of files in the `preprocessed_hansard` folder. Bold markup will then be processed in the next step to determine segments.
3. Run `python3 generate_tabular.py XX-XX-XX-XX`, where XX-XX-XX-XX is the session code. This will generate analysis files in the `analysis_hansard/XX-XX-XX-XX` folder and production files in the `release/XX-XX-XX-XX` folder.
4. Due to the irregularity in formatting across the Hansards, most likely there are warnings to be resolved when running `generate_tabular.py`. Resolve them by editing the preprocessed files. Most often you have to remove the bold markup for words that should not be marked as bold, since we use boldness to detect speakers and titles.
5. Additional checks can be done by checking the `DEWAN` statements, the `speakers.csv` and `category.csv`. Another good check if to go through the annotations (by searching for `[`) in `hansard.csv`.

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

# Usage
- Run preprocess.py to get the four output files of plaintext, binary bold and italic files (as 0, 1, or whitespaces). This file will only process the content from DOA onwards (ignores table of contents and MP attendance).

# Edits
- 12112019 replaced header dates from 12.11.201 to 12.11.2019