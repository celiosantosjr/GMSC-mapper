import pandas as pd

from os import path


def fixdf(x):
    x = x.dropna()
    x = x.drop_duplicates()
    return ','.join(x)
    
    
def formatlabel(x):
    x = x.split(',')
    x = list(set(x))
    x = sorted(x)
    return ','.join(x)
    
        
def smorf_habitat(outdir, habitatfile, resultfile):
    habitat_file = path.join(outdir, "habitat.out.smorfs.tsv")	

    result = pd.read_csv(resultfile,
                         sep='\t',
                         header=None)
                         
    result.rename({0: 'qseqid', 1: 'sseqid'},
                  axis=1,
                  inplace=True)
                         
    reader =  pd.read_table(habitatfile,
                            sep="\t",
                            chunksize=5_000_000,
                            header=None,
                            names=['sseqid', 'habitat'])

    output_list = []
    for chunk in reader:
        output_chunk = result.merge(on='sseqid',
                                    right=chunk,
                                    how='left')
        output_chunk = output_chunk[['qseqid', 'habitat']]
        output_list.append(output_chunk)
        
    output = pd.concat(output_list,
                       axis=0)
    
    output = output.sort_values(by='qseqid')
    
    output = output.groupby('qseqid',
                            as_index=False,
                            sort=False)
    
    output = output.agg({'habitat':lambda x : fixdf(x)})
    output['habitat'] = output['habitat'].apply(lambda x: formatlabel(x))
    
    output.to_csv(habitat_file,
                  sep='\t',
                  index=False)

    wdf = output['habitat'].apply(lambda x: len(x.split(',')))
    number_dict = dict(wdf.value_counts())
    number_dict_normalize = dict(wdf.value_counts(normalize=True))

    if 1 in number_dict.keys():
        single_number = number_dict[1]
        single_percentage = number_dict_normalize[1]
    else:
        single_number = 0
        single_percentage = 0
        
    multi_number = output['habitat'].size - single_number
    multi_percentage = 1 - single_percentage
    
    return (single_number, single_percentage, multi_number, multi_percentage)
    
