## Usage
Usage for now, will generalise later
1. Run `hansard_0_download.py` to download all session files.
2. Run `generate_markup.py`, remember to specify which session to process. This will add markup tags to bold and italic text, output as a file in the `output_hansard` folder. Bold markup will then be processed in the later step as segments.
3. Run `generate_hansard.py`, remember to specify which session to process. This will generate 3 files in the `analysis_hansard` folder: parquet, logs and output (string representation of Pandas DataFrame)

### Notes

- As of 14 July 2022, 17 November 2021 (14-04-02-15) has the last _Penyata Rasmi_; the statements after all have the status _Naskhah belum disemak_
- Categories encountered are, in their order of appearance in _KANDUNGAN_
  - JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN
  - JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN,
  - RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT,
  - USUL-USUL,
  - RANG UNDANG-UNDANG