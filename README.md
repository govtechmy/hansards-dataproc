## Usage
Usage for now, will generalise later
1. Install requirements `pip install -r requirements.txt`
2. Run `main.py`
3. Find `output/failed.txt`. Investigate and resolve errors by running `generate_tabular.py` with a specific session and fix by editing the markup files in the `preprocessed` folders.

### To run a specific session only
1. Run `download_hansard.py` to download all session files into `src_hansard`.
2. Run `generate_markup.py`, remember to specify which session to process. This will add markup tags to bold and italic text, output as a folder of files in the `preprocessed_hansard` folder. Bold markup will then be processed in the later step as segments.
3. Run `generate_tabular.py`, remember to specify which session to process. This will generate 3 files in a folder in the `analysis_hansard` folder: parquet, logs and output (string representation of Pandas DataFrame)

### Notes

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