import subprocess
import argparse
import sys
sys.path.append("..")
import os
from os import path
import pandas as pd
import tempfile
from atomicwrites import atomic_write

_ROOT = path.abspath(path.join(os.getcwd(), ".."))

def parse_args(args):
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='GMSC-mapper')
    subparsers = parser.add_subparsers(title='GMSC-mapper subcommands',
                                       dest='cmd',
                                       metavar='')

    cmd_create_db = subparsers.add_parser('createdb', 
                                          help='Create target database')
    cmd_create_db.add_argument('-i',
                               required=True,
                               help='Path to the GMSC 90AA FASTA file.',
                               dest='target_faa',
                               default = None)
    cmd_create_db.add_argument('-o', '--output',
                               required=False,
                               help='Path to database output directory.',
                               dest='output',
                               default = path.join(_ROOT, 'db'))
    cmd_create_db.add_argument('-m', '--mode',
                               required=True,
                               help='Alignment tool(Diamond/MMseqs2)',
                               dest='mode',
                               default = None)

    parser.add_argument('-i', '--input',
                        required=False,
                        help='Path to the input genome contig sequence FASTA file.',
                        dest='genome_fasta',
                        default = None)

    parser.add_argument('--nt-genes', '--nt_genes',
                        required=False,
                        help='Path to the input nucleotide gene sequence FASTA file.',
                        dest='nt_input',
                        default=None)

    parser.add_argument('--aa-genes', '--aa_genes',
                        required=False,
                        help='Path to the input amino acid sequence FASTA file.',
                        dest='aa_input',
                        default=None)

    parser.add_argument('--nofilter','--nofilter',action='store_true', help='Use this if no need to filter <100aa input sequences')

    parser.add_argument('--tool', '--tool',
                        required=False,
                        choices=['diamond', 'mmseqs'],
                        help='Sequence alignment tool(Diamond/MMseqs).',
                        dest='tool',
                        default='diamond')

    parser.add_argument('--db', '--db',
                        required=False,
                        help='Path to the GMSC database file.',
                        dest='database',
                        default=None)

    parser.add_argument('-s', '--sensitivity',
                        required=False,
                        help='Sensitivity.',
                        dest='sensitivity',
                        default=None)

    parser.add_argument('--id', '--id',
                        required=False,
                        help='Minimum identity to report an alignment(range 0.0-1.0).',
                        dest='identity',
                        default=0.0)

    parser.add_argument('--cov', '--cov',
                        required=False,
                        help='Minimum coverage to report an alignment(range 0.0-1.0).',
                        dest='coverage',
                        default=0.9)

    parser.add_argument('-e', '--evalue',
                        required=False,
                        help='Maximum e-value to report alignments(default=0.00001).',
                        dest='evalue',
                        default=0.00001)

    parser.add_argument('--outfmt', '--outfmt',
                        required=False,
                        help='Output format of alignment result.\nDiamond default is `6,qseqid,sseqid,full_qseq,full_sseq,qlen,slen,pident,length,evalue,qcovhsp,scovhsp`.\nMMseqs default is `query,target,qseq,tseq,qlen,tlen,fident,alnlen,evalue,qcov,tcov`.\nThe first two column in result format of Diamond/MMseqs must be `qseqid`/`query` and `sseqid`/`target`.',
                        dest='outfmt',
                        default=None)   

    parser.add_argument('--habitat', '--habitat',
                        required=False,
                        help='Path to the habitat file',
                        dest='habitat',
                        default=path.join(_ROOT, 'db/ref_habitat.tsv.xz'))
    parser.add_argument('--nohabitat','--nohabitat',action='store_true', help='Use this if no need to annotate habitat')

    parser.add_argument('--taxonomy', '--taxonomy',
                        required=False,
                        help='Path to the taxonomy file',
                        dest='taxonomy',
                        default=path.join(_ROOT, 'db/ref_taxonomy.tsv.xz'))
    parser.add_argument('--notaxonomy', '--notaxonomy',action='store_true', help='Use this if no need to annotate taxonomy')

    parser.add_argument('--quality', '--quality',
                        required=False,
                        help='Path to the quality file',
                        dest='quality',
                        default=path.join(_ROOT, 'db/ref_quality.tsv.xz'))
    parser.add_argument('--noquality', '--noquality',action='store_true', help='Use this if no need to annotate quality')

    parser.add_argument('-o', '--output',
                        required=False,
                        help='Output directory (will be created if non-existent)',
                        dest='output',
                        default=path.join(_ROOT, 'output'))	

    parser.add_argument('-t', '--threads',
                        required=False,
                        help='Number of CPU threads(default=3).',
                        dest='threads',
                        default=3)		
    return parser.parse_args()

def check_install():
    from shutil import which
    import sys
    
    has_mmseqs = False
    has_diamond = False
    dependencies = ['diamond', 'mmseqs']
    print("Looking for dependencies...")

    for dep in dependencies:
        p = which(dep)
        if p:
            if dep == 'diamond':
                has_diamond = True
            if dep == 'mmseqs':
                has_mmseqs = True
    if not has_diamond and not has_mmseqs:
        sys.stderr.write('GMSC-mapper Error: Neither diamond nor mmseqs appear to be available!\n'
                        'At least one of them is necessary to run GMSC-mapper.\n')
        sys.exit(1)
    elif has_diamond and not has_mmseqs:
        print('Warning: mmseqs does not appear to be available.You can only use the `--tool diamond` option(default).')
    elif not has_diamond and has_mmseqs:
        print('Warning: diamond does not appear to be available.You can only use the `--tool mmseqs` option.')
    else:
        print('Dependencies installation is OK\n')
    return has_diamond,has_mmseqs

def validate_args(args,has_diamond,has_mmseqs):
    def expect_file(f):
        if not os.path.exists(f):
            sys.stderr.write(f"GMSC-mapper Error: Expected file '{f}' does not exist\n")
            sys.exit(1)
    
    if not args.genome_fasta and not args.aa_input and not args.nt_input:
        pass
    elif args.genome_fasta and not args.aa_input and not args.nt_input:
        expect_file(args.genome_fasta)
    elif args.aa_input and not args.genome_fasta and not args.nt_input:
        expect_file(args.aa_input)
    elif args.nt_input and not args.genome_fasta and not args.aa_input:
        expect_file(args.nt_input)
    else:
        sys.stderr.write("GMSC-mapper Error: --input or --aa-genes or --nt_genes shouldn't be assigned at the same time\n")
        sys.exit(1)
    
    if args.tool == "diamond" and not has_diamond:
        sys.stderr.write("GMSC-mapper Error:diamond is not available.Please add diamond into your path or use the `--tool mmseqs` option.\n")
        sys.exit(1)       
    if args.tool == "mmseqs" and not has_mmseqs:
        sys.stderr.write("GMSC-mapper Error:mmseqs is not available.Please add mmseqs into your path or use the `--tool diamond` option(default).\n")
        sys.exit(1)

    if args.database:
        expect_file(args.database) 
    
    if args.outfmt:
        keywords = args.outfmt.split(",")
        if args.tool == "diamond":
            if  keywords[0] != "6" or keywords[1] != "qseqid" or keywords[2] != "sseqid":
                sys.stderr.write("GMSC-mapper Error:Outfmt value should be 6 (BLAST tabular format).And the first two columns of output should be `qseqid` and `sseqid`.\n")
                sys.exit(1)                
        if args.tool == "mmseqs":
            if  keywords[0] != "query" or keywords[1] != "target":
                sys.stderr.write("GMSC-mapper Error:The first two columns of output should be `query` and `target`.\n")
                sys.exit(1)             

    if not args.nohabitat and args.habitat:
        expect_file(args.habitat)

    if not args.notaxonomy and args.taxonomy:
        expect_file(args.taxonomy)

    if not args.noquality and args.quality:
        expect_file(args.quality)

def create_db(arguments):
    if not os.path.exists(arguments.output):
        os.makedirs(arguments.output)
    out_db = path.join(arguments.output,"targetdb")

    if arguments.mode == "diamond":
        print('Start creating Diamond database...')
        subprocess.check_call([
            'diamond','makedb',
            '--in',arguments.target_faa,
            '-d',out_db]) 
        print('\nDiamond database has been created successfully.\n')
    if arguments.mode == "mmseqs":
        print('Start creating MMseqs database...')
        subprocess.check_call([
            'mmseqs','createdb',
            arguments.target_faa,
            out_db]) 
        print('\nMMseqs database has been created successfully.\n')

def flatten(items, ignore_types=(str, bytes)):
    from collections.abc import Iterable
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, ignore_types):
            yield from flatten(x)
        else:
            yield x

def uncompress(input,tmpdir):
    import gzip
    import bz2
    import lzma

    if input.endswith('.gz'):
        print('Start uncompression...')
        with gzip.GzipFile(input) as ifile:
            open(tmpdir + '/input.fasta', "wb+").write(ifile.read())
        input = tmpdir + '/input.fasta'
        print('Uncompression has done.\n')

    if input.endswith('.bz2'):
        print('Start uncompression...')
        with bz2.BZ2File(input) as ifile:
            open(tmpdir + '/input.fasta', "wb+").write(ifile.read())
        input = tmpdir + '/input.fasta'
        print('Uncompression has done.\n')

    if input.endswith('.xz'):
        print('Start uncompression...')
        with lzma.open(input, 'rb') as ifile:
            open(tmpdir + '/input.fasta', "wb+").write(ifile.read())
        input = tmpdir + '/input.fasta'	
        print('Uncompression has done.\n')
 
    return input

def predict(args,tmpdir):
    from gmsc_mapper.predict import predict_genes,filter_smorfs
    print('Start smORF prediction...')
    predicted_smorf = path.join(tmpdir,"predicted.smorf.faa")
    filtered_smorf = path.join(args.output,"predicted.filterd.smorf.faa")
    predict_genes(args.genome_fasta,predicted_smorf)
    if not path.getsize(predicted_smorf):
        sys.stderr.write("GMSC-mapper Error:No smORFs have been predicted.Please check your input file.\n")
        sys.exit(1)          
    else:
        filter_smorfs(predicted_smorf, filtered_smorf)
    if not path.getsize(filtered_smorf):
        sys.stderr.write("GMSC-mapper Error:No smORFs remained after filtering by length(<100aa).\n")
        sys.exit(1)  
    else:
        print('\nsmORF prediction has done.\n')
    return filtered_smorf

def translate_gene(args,tmpdir):
    from gmsc_mapper.translate import translate_gene
    print('Start gene translation...')
    translated_file = translate_gene(args.nt_input,tmpdir)
    print('Gene translation has done.\n')
    return translated_file

def filter_length(queryfile,tmpdir,N):
    from gmsc_mapper.filter_length import filter_length
    print('Start length filter...')
    filtered_file = filter_length(queryfile,tmpdir,N)
    print('Length filter has done.\n')
    return filtered_file

def mapdb_diamond(args,queryfile):
    print('Start smORF mapping...')
 
    resultfile = path.join(args.output,"diamond.out.smorfs.tsv")

    subprocess.check_call([x for x in flatten([
        'diamond','blastp',
        '-q',queryfile,
        '-d',args.database,
        '-o',resultfile,
        args.sensitivity,
        '-e',str(args.evalue),
        '--id',str(float(args.identity)*100),
        '--query-cover',str(float(args.coverage)*100),
        '--subject-cover',str(float(args.coverage)*100),
        '-p',str(args.threads),
        '--outfmt',args.outfmt.split(',')])])  

    print('\nsmORF mapping has done.\n')
    return resultfile

def mapdb_mmseqs(args,queryfile,tmpdir):
    print('Start smORF mapping...')
    
    querydb = path.join(tmpdir,"query.db")
    resultdb = path.join(tmpdir,"result.db")
    tmp = path.join(tmpdir,"tmp","")
    resultfile = path.join(args.output,"mmseqs.out.smorfs.tsv")

    subprocess.check_call([
        'mmseqs','createdb',queryfile,querydb]) 

    subprocess.check_call([
        'mmseqs','search',
        querydb,
        args.database,
        resultdb,
        tmp,
        '-s',str(args.sensitivity),
        '-e',str(args.evalue),
        '--min-seq-id',str(args.identity),
        '-c',str(args.coverage),
        '--threads',str(args.threads)])  

    subprocess.check_call([
        'mmseqs','convertalis',
        querydb,
        args.database,
        resultdb,
        resultfile,
        '--format-output',args.outfmt])		

    print('\nsmORF mapping has done.\n')
    return resultfile

def generate_fasta(output,queryfile,resultfile):
    import pandas as pd
    from gmsc_mapper.fasta import fasta_iter

    try:
        result = pd.read_csv(resultfile, sep='\t',header=None)
    except:
        print('GMSC-mapper Warning: There is no alignment results between your input sequences and GMSC.\n')
        sys.exit(1)

    print('Start smORF fasta file generating...')
    fastafile = path.join(output,"mapped.smorfs.faa")

    smorf_id = set(result.iloc[:, 0].tolist())
    
    with open(fastafile,"wt") as f:
        for ID,seq in fasta_iter(queryfile):
            if ID in smorf_id:
                f.write(f'>{ID}\n{seq}\n')
    print('smORF fasta file generating has done.\n')
    return fastafile

def habitat(args,resultfile):
    from gmsc_mapper.map_habitat import smorf_habitat
    print('Start habitat annotation...')
    single_number,single_percentage,multi_number,multi_percentage = smorf_habitat(args.output,args.habitat,resultfile)
    print('habitat annotation has done.\n')
    return single_number,single_percentage,multi_number,multi_percentage 

def taxonomy(args,resultfile,tmpdirname):
    from gmsc_mapper.map_taxonomy import deep_lca,taxa_summary
    print('Start taxonomy annotation...')
    deep_lca(args.taxonomy,args.output,resultfile,tmpdirname)
    annotated_number,rank_number,rank_percentage = taxa_summary(args.output)
    print('taxonomy annotation has done.\n')
    return annotated_number,rank_number,rank_percentage

def quality(args,resultfile):
    from gmsc_mapper.map_quality import smorf_quality
    print('Start quality annotation...')
    number,percentage = smorf_quality(args.output,args.quality,resultfile)
    print('quality annotation has done.\n')
    return number,percentage

def predicted_smorf_count(file_name):
    out = subprocess.getoutput("wc -l %s" % file_name)
    return int(out.split()[0])

def main(args=None):
    if args is None:
        args = sys.argv
    args = parse_args(args)
    if not args.cmd and (not args.genome_fasta and not args.aa_input and not args.nt_input):
        sys.stderr.write("GMSC-mapper Error: Please see gmsc-mapper -h. Assign the subcommand or input file.\n")
        sys.exit(1)             
    has_diamond,has_mmseqs = check_install()

    if args.cmd == 'createdb':
        create_db(args)

    if not args.cmd:
        validate_args(args,has_diamond,has_mmseqs)

        if args.tool == 'diamond':
            if args.database is None:
                args.database = path.join(_ROOT, 'db/targetdb.dmnd')
            if args.sensitivity is None:
                args.sensitivity = '--more-sensitive'
            if args.sensitivity == '1':
                args.sensitivity = '--fast'
            if args.sensitivity == '2':
                args.sensitivity = '--mid-sensitive'
            if args.sensitivity == '3':
                args.sensitivity = '--default'
            if args.sensitivity == '4':
                args.sensitivity = '--sensitive'
            if args.sensitivity == '5':
                args.sensitivity = '--more-sensitive'
            if args.sensitivity == '6':
                args.sensitivity = '--very-sensitive'
            if args.sensitivity == '7':
                args.sensitivity = '--ultra-sensitive'
            if args.outfmt is None:
                args.outfmt = '6,qseqid,sseqid,full_qseq,full_sseq,qlen,slen,pident,length,evalue,qcovhsp,scovhsp'
        if args.tool == 'mmseqs':
            if args.database is None:
                args.database = path.join(_ROOT, 'db/targetdb')
            if args.sensitivity is None:
                args.sensitivity = 5.7
            if args.outfmt is None:
                args.outfmt = 'query,target,qseq,tseq,qlen,tlen,fident,alnlen,evalue,qcov,tcov'

        if not os.path.exists(args.output):
            os.makedirs(args.output)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                summary = []
                summary.append(f'# Total number')
                if args.genome_fasta:
                    args.genome_fasta = uncompress(args.genome_fasta,tmpdir)
                    queryfile = predict(args,tmpdir)
                    smorf_number = int(predicted_smorf_count(queryfile)/2)
                    summary.append(f'{str(smorf_number)} smORFs are predicted in total.')
                if args.nt_input:
                    args.nt_input = uncompress(args.nt_input,tmpdir)
                    if not args.nofilter:
                        args.nt_input = filter_length(args.nt_input,tmpdir,303)
                    queryfile = translate_gene(args,tmpdir)  
                if args.aa_input:
                    args.aa_input = uncompress(args.aa_input,tmpdir)
                    if not args.nofilter:
                        args.aa_input = filter_length(args.aa_input,tmpdir,100)
                    queryfile = args.aa_input

                if args.tool == 'diamond':
                    resultfile = mapdb_diamond(args,queryfile)
                if args.tool == 'mmseqs':
                    resultfile = mapdb_mmseqs(args,queryfile,tmpdir)

                fastafile = generate_fasta(args.output,queryfile,resultfile)
                smorf_number = int(predicted_smorf_count(fastafile)/2)
                summary.append(f'{str(smorf_number)} smORFs are aligned against GMSC in total.\n')

                if not args.noquality:
                    summary.append(f'# Quality')
                    number,percentage = quality(args,resultfile)	
                    summary.append(f'{str(number)}({str(round(percentage*100,2))}%) aligned smORFs are high quality.\n')

                if not args.nohabitat:
                    summary.append(f'# Habitat')
                    single_number,single_percentage,multi_number,multi_percentage = habitat(args,resultfile)
                    summary.append(f'{str(single_number)}({str(round(single_percentage*100,2))}%) aligned smORFs are single-habitat.')
                    summary.append(f'{str(multi_number)}({str(round(multi_percentage*100,2))}%) aligned smORFs are multi-habitat.\n')

                if not args.notaxonomy:
                    summary.append(f'# Taxonomy')
                    annotated_number,rank_number,rank_percentage = taxonomy(args,resultfile,tmpdir)	
                    summary.append(str(annotated_number)+'('+str(round((1-rank_percentage['no rank'])*100,2))+'%) aligned smORFs have taxonomy annotation.')
                    summary.append(str(rank_number['kingdom'])+'('+str(round(rank_percentage['kingdom']*100,2))+'%) aligned smORFs are annotated on kingdom.')
                    summary.append(str(rank_number['phylum'])+'('+str(round(rank_percentage['phylum']*100,2))+'%) aligned smORFs are annotated on phylum.')
                    summary.append(str(rank_number['class'])+'('+str(round(rank_percentage['class']*100,2))+'%) aligned smORFs are annotated on class.')
                    summary.append(str(rank_number['order'])+'('+str(round(rank_percentage['order']*100,2))+'%) aligned smORFs are annotated on order.')
                    summary.append(str(rank_number['family'])+'('+str(round(rank_percentage['family']*100,2))+'%) aligned smORFs are annotated on family.')
                    summary.append(str(rank_number['genus'])+'('+str(round(rank_percentage['genus']*100,2))+'%) aligned smORFs are annotated on genus.')
                    summary.append(str(rank_number['species'])+'('+str(round(rank_percentage['species']*100,2))+'%) aligned smORFs are annotated on species.')

                with atomic_write(f'{args.output}/summary.txt', overwrite=True) as ofile:
                    for s in summary:
                        print(s)
                        ofile.write(f'{s}\n')		

            except Exception as e:
                sys.stderr.write('GMGC-mapper Error: ')
                sys.stderr.write(str(e))
                sys.stderr.write('\n')
                sys.exit(1)		

if __name__ == '__main__':    
    main(sys.argv)