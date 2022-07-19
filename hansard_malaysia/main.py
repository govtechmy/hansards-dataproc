import download_hansard
import pandas as pd
import generate_markup
import generate_tabular

if __name__ == "__main__":
    # This is for bulk actions
    # to manage a specific session, please run generate_markup and generate_tabular on their own

    # comment line below if PDFs have been downloaded
    # download_hansard.download_hansards()

    df = pd.read_csv('sessions.csv', parse_dates=['date'])
    sessions = df.session.tolist()
    status = {}
    failed = []
    rejected = []
    success = []

    # generate markup for all files
    # comment section below if files have been preprocessed
    for session in sessions:
        print("Processing", session)
        # generate_markup.process_file(session)

    print("All markup complete. Begin parsing markup")
    for session in sessions:
        print("Parsing", session)
        try:
            status[session] = generate_tabular.process_file(session)
            if status[session] == -1:
                # not final version, cannot process
                print(session, "rejected")
                rejected.append(session)
            else:
                print(session, "success")
                success.append(session)
        except AssertionError as err:
            print("Errors detected:", err)
            print(session, "failed")
            failed.append(session)
            status[session] = 0

    output = "Total processed: " + str(len(sessions)) + '\n'
    output += "Total success: " + str(len(success)) + '\n'
    output += "Total rejected: " + str(len(rejected)) + '\n'
    output += "Total failed: " + str(len(failed)) + '\n\n'
    print(output)

    with open('output/success.txt', 'w') as f:
        f.write('\n'.join(success))

    with open('output/rejected.txt', 'w') as f:
        f.write('\n'.join(rejected))

    with open('output/failed.txt', 'w') as f:
        f.write('\n'.join(failed))
