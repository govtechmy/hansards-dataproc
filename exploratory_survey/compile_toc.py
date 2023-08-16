"""Compile the unique categories from get_categories.py.
"""

import json
import pandas as pd

if __name__ == "__main__":
    with open("categories.txt", 'r') as f:
        categories = f.read().split('\n')
    # preprocessing to remove : and strip
    categories = [x.strip().rstrip(':').strip() for x in categories]
    # delete empty category
    categories = [x for x in categories if x != '']
    # delete typo
    # 12112018
    categories = [x for x in categories if x != 'USUL-USUL:P']
    # get the count of each category
    category_count = [(x, categories.count(x)) for x in categories]
    category_count = list(set(category_count))
    # export the category count to csv using pandas
    df = pd.DataFrame(category_count, columns=['category', 'count'])
    df.to_csv("category_count.csv", index=False)
    categories = list(set(categories))
    categories.sort()
    # dump to json
    with open("../categories.json", 'w') as f:
        json.dump(categories, f, indent=4)
