# Find all the PDF files in the DATA_DIR directory
import datetime
import os

DATA_DIR = 'data'

def find_pdf_files(directory=DATA_DIR):
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.pdf'):
                pdf_files.append(os.path.join(root, filename))
    return pdf_files


# Each of the PDF files that has a name that starts with MM-DD-YYYY
# will have its created date replaced with the date in the filename.
def update_pdf_dates(directory=DATA_DIR):
    pdf_files = find_pdf_files(directory)
    for pdf_file in pdf_files:
        print(f"Updating date for {pdf_file}")
        filename = os.path.basename(pdf_file)
        if filename.startswith(tuple(f"{m:02d}-{d:02d}-{y} " for y in range(2000, 2030) for m in range(1, 13) for d in range(1, 32))):
            m,d,y = filename.split('-')[:3]
            y = y.split(' ')[0]  # Remove any trailing space or text after the date
            new_date = datetime.datetime(int(y), int(m), int(d)).timestamp()
            os.utime(pdf_file, (new_date, new_date))


if __name__ == "__main__":
    # get the current directory
    directory = os.getcwd()
    print(f"Updating PDF dates in directory: {directory}")
    
    # Update the PDF dates based on the filenames

    update_pdf_dates(directory)
    print("PDF dates updated based on filenames.")
