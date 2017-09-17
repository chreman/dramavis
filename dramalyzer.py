#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# dramavis by frank fischer (@umblaetterer) & christopher kittel (@chris_kittel)

__author__ = "Christopher Kittel <web at christopherkittel.eu>, Frank Fischer <ffischer at hse.ru>"
__copyright__ = "Copyright 2017"
__license__ = "MIT"
__version__ = "0.4 (beta)"
__maintainer__ = "Frank Fischer <ffischer at hse.ru>"
__status__ = "Development" # 'Development', 'Production' or 'Prototype'

from lxml import etree
import os
import glob
import pandas as pd
import networkx as nx
import csv
from itertools import chain, zip_longest
from collections import Counter
import argparse
from superposter import plotGraph, plot_superposter
import logging
import numpy
from tqdm import tqdm

from linacorpus import LinaCorpus, Lina




class CorpusAnalyzer(LinaCorpus):

    def __init__(self, inputfolder, outputfolder, logpath):
        super(CorpusAnalyzer, self).__init__(inputfolder, outputfolder)
        self.logger = logging.getLogger("corpusAnalyzer")
        formatter = logging.Formatter('%(asctime)-15s %(name)s [%(levelname)s]'
                                      '%(message)s')
        fh = logging.FileHandler(logpath)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logpath = logpath


    def analyze_dramas(self):
        """
        Reads all XMLs in the inputfolder,
        returns an iterator of lxml.etree-objects created with lxml.etree.parse("dramafile.xml").
        """
        # dramas = {}
        for dramafile in tqdm(self.dramafiles, desc="Dramas", mininterval=0.5):
            # ID, ps = parse_drama(tree, filename)
            # dramas[ID] = ps
            drama = DramaAnalyzer(dramafile, self.outputfolder, self.logpath)
            yield drama

    def get_central_characters(self):
        self.logger.info("Exporting character metrics.")
        dramas = self.analyze_dramas()
        header = [
                    'ID', 'author', 'title', 'year',
                    'frequency', 'degree', 'betweenness', 'closeness',
                    'central'
                 ]
        dfs = []
        for drama in dramas:
            temp_df = drama.graph_metrics.copy()
            for m in header[1:3]:
                temp_df[m] = drama.metadata.get(m)
            temp_df['year'] = drama.metadata.get('date_definite')
            for m in header[4:]:
                temp_df[m] = drama.get_top_ranked_chars()[m]
            temp_df['ID'] = drama.ID
            dfs.append(temp_df)
        df = pd.concat(dfs)
        df = df[header]
        df.index = df['ID']
        df.index.name = 'index'
        df.to_csv(os.path.join(self.outputfolder,
                               "central_characters.csv"), sep=";")

    def get_metrics(self):
        self.logger.info("Exporting corpus metrics.")
        dramas = self.analyze_dramas()
        df = pd.concat([d.graph_metrics for d in dramas])
        header =    [
                    'ID', 'author', 'title', 'subtitle', 'year', 'genretitle', 'filename',
                    'charcount', 'edgecount', 'maxdegree', 'avgdegree',
                    'clustering_coefficient', 'clustering_coefficient_random', 'avgpathlength', 'average_path_length_random', 'density',
                    'segment_count', 'count_type', 'all_in_index', 'central_character_entry_index', 'change_rate_mean', 'change_rate_std', 'final_scene_size_index',
                    'central_character', 'characters_last_in',
                    'connected_components'
                    ]
        df.index = df["ID"]
        df.index.name = "index"
        df.to_csv(os.path.join(self.outputfolder, "corpus_metrics"), sep=";")

    def get_individual_outputs(self):
        self.logger.info("Exporting individual drama plots and metrics.")
        for dramafile in tqdm(self.dramafiles, desc="Dramas", mininterval=0.5):
            # ID, ps = parse_drama(tree, filename)
            # dramas[ID] = ps
            drama = DramaAnalyzer(dramafile, self.outputfolder, self.logpath)
            drama.write_output()


class DramaAnalyzer(Lina):

    def __init__(self, dramafile, outputfolder, logpath):
        super(DramaAnalyzer, self).__init__(dramafile, outputfolder)
        self.logger = logging.getLogger("dramaAnalyzer")
        formatter = logging.Formatter('%(asctime)-15s %(name)s [%(levelname)s]'
                                      '%(message)s')
        fh = logging.FileHandler(logpath)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.n_personae = len(self.personae)
        self.centralities = pd.DataFrame(index = [p for p in self.personae])
        self.centralities.index.name = "name"
        self.randomization = 1000
        self.metrics = pd.DataFrame()
        self.G = self.create_graph()
        self.analyze_characters()
        self.get_character_frequencies()
        self.get_character_ranks()
        self.get_centrality_ranks()
        self.get_central_characters()
        self.graph_metrics = self.get_graph_metrics()

    def get_final_scene_size(self):
        last_scene_size = len(self.segments[-1])
        return last_scene_size / self.n_personae

    def get_drama_change_rate_metrics(self):
        change_rates = self.get_drama_change_rate()
        cr_mean = numpy.mean(change_rates)
        cr_std = numpy.std(change_rates)
        return cr_mean, cr_std

    def get_drama_change_rate(self):
        change_rates = []
        for x, y in zip_longest(self.segments[:-1], self.segments[1:]):
            s = set(x)
            t = set(y)
            u = s.intersection(t)
            cr = abs(len(s)-len(u)) + abs(len(u)-len(t))
            cr_sum = len(s.union(t))
            change_rates.append(cr/cr_sum)
        return change_rates

    def get_central_character_entry(self):
        central_character = self.get_central_character()
        for i, segment in enumerate(self.segments):
            if central_character in segment:
                i += 1
                central_character_entry_index = float(i/len(self.segments))
                return central_character_entry_index

    def get_central_character(self):
        # either that or hardcode
        ranks = [c for c in self.centralities.columns if c.endswith("rank")]
        # sum up all rank values per character, divide by nr. of rank metrics
        avg_ranks = self.centralities[ranks].sum(axis=1)/len(ranks)
        min_rank = min(avg_ranks)
        central_chars = avg_ranks[avg_ranks == min_rank].index.tolist()
        if len(central_chars) == 1:
            return central_chars[0]
        else:
            return "SEVERAL"

    def get_character_frequencies(self):
        self.centralities['frequency'] = 0
        frequencies = Counter(list(chain.from_iterable(self.segments)))
        for char, freq in frequencies.items():
            self.centralities.loc[char, 'frequency'] = freq

    def get_top_ranked_chars(self):
        top_ranked = {}
        # check whether metric should be sorted ascending(min) or descending(max)
        for metric in ['degree', 'closeness', 'betweenness', 'frequency']:
            cent_max = self.centralities[metric].max()
            top_char = self.centralities[self.centralities['closeness'] == cent_max].index.tolist()
            if len(top_char) != 1:
                top_ranked[metric] = "SEVERAL"
            else:
                top_ranked[metric] = top_char[0]
        top_ranked['central'] = self.get_central_character()
        return top_ranked

    def get_character_ranks(self):
        for metric in ['degree', 'closeness', 'betweenness', 'frequency']:
            # ascending: False for ranks by high (1) to low (N)
            # check ascending value for each metric
            self.centralities[metric+"_rank"] = self.centralities[metric].rank(method='dense', ascending=False)

    def get_centrality_ranks(self):
        self.centralities['avg_centrality_rank'] = self.centralities.apply(
                                            lambda x: (x['degree_rank'] +
                                                       x['closeness_rank'] +
                                                       x['betweenness_rank'])/3,
                                            axis=1)

    def get_central_characters(self):
        self.centralities['composite_centrality'] = self.centralities.apply(
                                        lambda x: (x['frequency_rank'] +
                                                   x['avg_centrality_rank'])/2,
                                        axis=1)

    def get_characters_all_in_index(self):
        appeared = set()
        for i, speakers in enumerate(self.segments):
            for sp in speakers:
                appeared.add(sp)
            if len(appeared) >= self.num_chars_total:
                i += 1
                all_in_index = float(i/len(self.segments))
                # print(all_in_index, len(self.segments), len(appeared), self.num_chars_total)
                return all_in_index

    def write_output(self):
        self.centralities.index = self.centralities["ID"]
        self.centralities.index.name = "index"
        self.graph_metrics.to_csv(os.path.join(
                                    self.outputfolder,
                                    "%s_%s_graph.csv" % (self.ID, self.title)))
        self.export_table(
                self.get_drama_change_rate(),
                "_".join([self.filepath, self.title,"change_rates"])+".csv")
        self.centralities.to_csv(
                os.path.join(
                            self.outputfolder,
                            "%s_%s_chars.csv" % (self.ID, self.title)
                            ))
        nx.write_edgelist(
                self.G,
                os.path.join(self.outputfolder,
                             "_".join([str(self.ID),
                             self.title,"edgelist"])+".csv"),
                delimiter=";",
                data=["weight"])
        plotGraph(
                self.G,
                filename=os.path.join(self.outputfolder,
                                      "_".join([str(self.ID),
                                      self.title])+".svg"))

    def export_table(self, t, filepath):
        with open(filepath, 'w') as f:  # Just use 'w' mode in 3.x
            csvwriter = csv.writer(f, delimiter=';')
            csvwriter.writerow(["segment", "change_rate"])
            for i, t in enumerate(t):
                csvwriter.writerow([i+1, t])

    def get_graph_metrics(self):
        graph_metrics = self.analyze_graph()
        graph_metrics["ID"] = self.ID
        graph_metrics["average_path_length_random"], graph_metrics["clustering_coefficient_random"] = self.randomize_graph(graph_metrics.get("charcount"), graph_metrics.get("edgecount"))
        graph_metrics["year"] = self.metadata.get("date_definite")
        graph_metrics["author"] = self.metadata.get("author")
        graph_metrics["title"] = self.title
        graph_metrics["filename"] = self.metadata.get("filename")
        graph_metrics["genretitle"] = self.metadata.get("genretitle")
        graph_metrics["subtitle"] = self.metadata.get("subtitle")
        graph_metrics["segment_count"] = self.metadata.get("segment_count")
        graph_metrics["count_type"] = self.metadata.get("count_type")
        graph_metrics["all_in_index"] = self.get_characters_all_in_index()
        graph_metrics["change_rate_mean"], graph_metrics["change_rate_std"] = self.get_drama_change_rate_metrics()
        graph_metrics["final_scene_size_index"] = self.get_final_scene_size()
        graph_metrics["central_character"] = self.get_central_character()
        graph_metrics["central_character_entry_index"] = self.get_central_character_entry()
        graph_metrics["characters_last_in"] = self.get_characters_last_in()
        return pd.DataFrame.from_dict(graph_metrics, orient='index').T

    def get_characters_last_in(self):
        last_chars = self.segments[-1]
        return ",".join(last_chars)

    def create_graph(self):
        """
        First creates a bipartite graph with scenes on the one hand,
        and speakers in one scene on the other.
        The graph is then projected into a unipartite graph of speakers,
        which are linked if they appear in one scene together.

        Returns a networkx weighted projected graph.
        """
        speakerset = self.segments

        B = nx.Graph()
        labels = {}
        for i, speakers in enumerate(speakerset):
            # speakers are Character objects
            source = str(i)
            targets = speakers
            # if args.debug:
            #     print("SOURCE, TARGET:", source, targets)

            if not source in B.nodes():
                B.add_node(source, bipartite=0)
                labels[source] = source

            for target in targets:
                if not target in B.nodes():
                    B.add_node(target, bipartite=1)
                B.add_edge(source, target)

        # if args.debug:
        #     print("EDGES:", B.edges())
        scene_nodes = set(n for n,d in B.nodes(data=True) if d['bipartite']==0)
        person_nodes = set(B) - scene_nodes
        nx.is_bipartite(B)
        G = nx.bipartite.weighted_projected_graph(B, person_nodes)
        return G

    def analyze_graph(self):
        """
        Computes various network metrics for a graph G,
        returns a dictionary:
        values =
        {
            "charcount" = len(G.nodes()),
            "edgecount" = len(G.edges()),
            "maxdegree" = max(G.degree().values()) or "NaN" if ValueError: max() arg is an empty sequence,
            "avgdegree" = sum(G.degree().values())/len(G.nodes()) or "NaN" if ZeroDivisionError: division by zero,
            "density" = nx.density(G) or "NaN",
            "avgpathlength" = nx.average_shortest_path_length(G) or "NaN" if NetworkXError: Graph is not connected,
                                then it tries to get the average_shortest_path_length from the giant component,
            "avgpathlength" = nx.average_shortest_path_length(max(nx.connected_component_subgraphs(G), key=len))
                                    except NetworkXPointlessConcept: ('Connectivity is undefined ', 'for the null graph.'),
            "clustering_coefficient" = nx.average_clustering(G) or "NaN" if ZeroDivisionError: float division by zero
        }
        """
        G = self.G
        values = {}
        values["charcount"] = len(G.nodes())
        values["edgecount"] = len(G.edges())
        try:
            values["maxdegree"] = max(G.degree().values())
        except:
            self.logger.error("ID %s ValueError: max() arg is an empty sequence" % self.ID)
            values["maxdegree"] = "NaN"

        try:
            values["avgdegree"] = sum(G.degree().values())/len(G.nodes())
        except:
            self.logger.error("ID %s ZeroDivisionError: division by zero" % self.ID)
            values["avgdegree"] = "NaN"

        try:
            values["density"] = nx.density(G)
        except:
            values["density"] = "NaN"

        try:
            values["avgpathlength"] = nx.average_shortest_path_length(G)
        except nx.NetworkXError:
            self.logger.error("ID %s NetworkXError: Graph is not connected." % self.ID)
            try:
                self.randomization = 50
                values["avgpathlength"] = nx.average_shortest_path_length(
                            max(nx.connected_component_subgraphs(G), key=len))
            except:
                values["avgpathlength"] = "NaN"
        except:
            self.logger.error("ID %s NetworkXPointlessConcept: ('Connectivity is "
                              "undefined for the null graph.')"  % self.ID)
            values["avgpathlength"] = "NaN"

        try:
            values["clustering_coefficient"] = nx.average_clustering(G)
        except:
            self.logger.error("ID %s ZeroDivisionError: float division by zero" % self.ID)
            values["clustering_coefficient"] = "NaN"
        values["connected_components"] = nx.number_connected_components(G)
        return values

    def analyze_characters(self):
        """
        Computes per-character metrics of a graph G,
        returns dictionary of dictionaries:
        character_values =
        {
            "betweenness" = nx.betweenness_centrality(G),
            "degree" = nx.degree(G),
            "closeness" = nx.closeness_centrality(G)
        }
        """
        for metric in ['betweenness', 'degree', 'closeness']:
            self.centralities[metric] = 0
        for char, metric in nx.betweenness_centrality(self.G).items():
            self.centralities.loc[char, 'betweenness'] = metric
        for char, metric in nx.degree(self.G).items():
            self.centralities.loc[char, 'degree'] = metric
        for char, metric in nx.closeness_centrality(self.G).items():
            self.centralities.loc[char, 'closeness'] = metric

    def transpose_dict(self, d):
        """
        Transpose dict of character-network metrics to an exportable dict,
        essentially transposes rows and columns of the character.csv.
        """
        td = {}
        try:
            for cent, chars in d.items():
                for char in chars:
                    td[char] = {}
        except:
            pass
        try:
            for cent, chars in d.items():
                for char, value in chars.items():
                    td[char][cent] = value
        except:
            pass
        return td

    def randomize_graph(self, n, e):
        """
        Creates 1000 random graphs with networkx.gnm_random_graph(nodecount, edgecount),
        and computes average_clustering_coefficient and average_shortest_path_length,
        to compare with drama-graph.
        Returns a tuple:
        randavgpathl, randcluster = (float or "NaN", float or "NaN")
        """
        randcluster = 0
        randavgpathl = 0
        # what is c, what is a, what is n, what is e?
        # e=edges?, c=clustering_coefficient?, a=average_shortest_path_length?
        c = 0
        a = 0

        for i in tqdm(range(self.randomization), desc="Randomization"):
            R = nx.gnm_random_graph(n, e)
            try:
                randcluster += nx.average_clustering(R)
                c += 1
            except ZeroDivisionError:
                pass
            j = 0
            while True:
                j += 1
                try:
                    R = nx.gnm_random_graph(n, e)
                    randavgpathl += nx.average_shortest_path_length(R)
                    a += 1
                except:
                    pass
                else:
                    break
                if j > 50:
                    randavgpathl = "NaN"
                    break
        try:
            randcluster = randcluster / c
        except:
            randcluster = "NaN"
        try:
            randavgpathl = randavgpathl / a
        except:
            randavgpathl = "NaN"
        return randavgpathl, randcluster
