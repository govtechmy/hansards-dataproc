import download_hansard
import pandas as pd
import generate_markup
import generate_tabular

if __name__ == "__main__":
    # uncomment line below if PDFs have not been downloaded
    # download_hansard.download_hansards()

    df = pd.read_csv('sessions.csv', parse_dates=['date'])
    sessions = df.session.tolist()
    status = {}
    failed = []
    for session in sessions:
        print("Processing", session)
        print("Adding markup")
        generate_markup.process_file(session)
        print("Markup complete. Parsing markup")
        try:
            generate_tabular.process_file(session)
            print(session, "success")
            status[session] = 1
        except AssertionError as err:
            print("Errors detected:", err)
            print("Quiting", session)
            failed.append(session)
            status[session] = 0

    output = "Total processed: " + len(sessions) + '\n'
    output = "Total success: " + len(sessions) - len(failed) + '\n'
    output += "Total failed: " + len(failed) + '\n\n'
    output += "FAILED:\n"
    for failure in failed:
        output += failure + '\n'
    with open('results.txt', 'w') as f:
        f.write(output)
