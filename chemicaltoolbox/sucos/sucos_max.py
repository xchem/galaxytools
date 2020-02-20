#!/usr/bin/env python
"""
Assess ligands against a second set of molecules using SuCOS scores.
This is a quite specialised function that is designed to take a set of potential follow up
compounds and compare them to a set of clustered fragment hits to help identify which follow up
ligands best map to the binding space of the hits.

The clustering of the fragment hits is expected to be performed with the sucos_cluster.py module
and will generate a set of SD files, one for each cluster of hits (presumably corresponding to a
binding pocket in the protein target).

Each molecule in the input ligands is then compared (using SuCOS) to each hit in the clusters. There
 are different modes which determine how the ligand is assessed.

In mode 'max' the hit with the best SuCOS score is identified. The output is a SD file with each of the ligands,
with these additional fields for each molecule:
Max_SuCOS_Score - the best score
Max_SuCOS_FeatureMap_Score - the feature map score for the hit that has the best SuCOS score
Max_SuCOS_Protrude_Score - the protrude volume for the hit that has the best SuCOS score
Max_SuCOS_Cluster - the name of the cluster SD file that contains the best hit
Max_SuCOS_Index - the index of the best hit in the SD file

In mode 'cum' the sum of all the scores is calculated and reported as the following properties for each molecule:
Cum_SuCOS_Score property: the sum of the SuCOS scores
Cum_SuCOS_FeatureMap_Score: the sum of the feature map scores
Cum_SuCOS_Protrude_Score: the sum of the protrude volume scores

If a molecule has no alignment to any of the clustered hits (all alignment scores of zero) then it is not
included in the results.


SuCOS is the work of Susan Leung.
GitHub: https://github.com/susanhleung/SuCOS
Publication: https://doi.org/10.26434/chemrxiv.8100203.v1
"""

import sucos, utils
import argparse, gzip, os
from rdkit import Chem


def process(inputfilename, clusterfilenames, outputfilename, mode):

    all_clusters = {}
    for filename in clusterfilenames:
        cluster = []
        cluster_file = utils.open_file_for_reading(filename)
        suppl = Chem.ForwardSDMolSupplier(cluster_file)
        i = 0
        for mol in suppl:
            i += 1
            if not mol:
                utils.log("WARNING: failed to generate molecule", i, "in cluster", filename)
                continue
            try:
                features = sucos.getRawFeatures(mol)
                cluster.append((mol, features))
            except:
                utils.log("WARNING: failed to generate features for molecule", i, "in cluster", filename)

        cluster_file.close()
        all_clusters[filename] = cluster

    input_file = utils.open_file_for_reading(inputfilename)
    suppl = Chem.ForwardSDMolSupplier(input_file)
    output_file = utils.open_file_for_writing(outputfilename)
    writer = Chem.SDWriter(output_file)

    comparisons = 0
    mol_num = 0

    for mol in suppl:
        mol_num += 1
        if not mol:
            utils.log("WARNING: failed to generate molecule", mol_num, "in input")
            continue
        try:
            query_features = sucos.getRawFeatures(mol)
        except:
            utils.log("WARNING: failed to generate features for molecule", mol_num, "in input")
            continue
        scores = [0, 0, 0]
        for clusterfilename in all_clusters:
            cluster = all_clusters[clusterfilename]
            index = 0
            for entry in cluster:
                hit = entry[0]
                ref_features = entry[1]
                index += 1
                comparisons += 1
                sucos_score, fm_score, vol_score = sucos.get_SucosScore(hit, mol,
                    tani=False, ref_features=ref_features, query_features=query_features)
                if mode == 'max':
                    if sucos_score > scores[0]:
                        scores[0] = sucos_score
                        scores[1] = fm_score
                        scores[2] = vol_score
                        cluster_name = clusterfilename
                        cluster_index = index
                elif mode == 'cum':
                    scores[0] += sucos_score
                    scores[1] += fm_score
                    scores[2] += vol_score
                else:
                    raise ValueError("Invalid mode: " + mode)

        if scores[0] > 0:
            if mode == 'max':
                cluster_file_name_only = cluster_name.split(os.sep)[-1]
                #utils.log("Max SuCOS:", scores[0], "FM:", scores[1], "P:", scores[2],"File:", cluster_file_name_only, "Index:", cluster_index)
                mol.SetDoubleProp("Max_SuCOS_Score", scores[0])
                mol.SetDoubleProp("Max_SuCOS_FeatureMap_Score", scores[1])
                mol.SetDoubleProp("Max_SuCOS_Protrude_Score", scores[2])
                mol.SetProp("Max_SuCOS_Cluster", cluster_file_name_only)
                mol.SetIntProp("Max_SuCOS_Index", cluster_index)

            else:
                #utils.log("Cum SuCOS:", scores[0], "FM:", scores[1], "P:", scores[2])
                mol.SetDoubleProp("Cum_SuCOS_Score", scores[0])
                mol.SetDoubleProp("Cum_SuCOS_FeatureMap_Score", scores[1])
                mol.SetDoubleProp("Cum_SuCOS_Protrude_Score", scores[2])

            writer.write(mol)

        else:
            utils.log("Molecule", mol_num, "did not overlay. Omitting from results")


    input_file.close()
    writer.flush()
    writer.close()
    output_file.close()

    utils.log("Completed", comparisons, "comparisons")


### start main execution #########################################

def main():
    parser = argparse.ArgumentParser(description='Max SuCOS scores with RDKit')
    parser.add_argument('-i', '--input', help='Input file to score in SDF format. Can be gzipped (*.gz).')
    parser.add_argument('-o', '--output', help='Output file in SDF format. Can be gzipped (*.gz).')
    parser.add_argument('-m', '--mode', choices=['max', 'cum'],
                        default='max', help='Score mode: max = best score, cum = sum of all scores')
    parser.add_argument('clusters', nargs='*', help="One or more SDF files with the clustered hits")

    args = parser.parse_args()
    utils.log("Max SuCOS Args: ", args)

    process(args.input, args.clusters, args.output, args.mode)


if __name__ == "__main__":
    main()