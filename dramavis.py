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

from linacorpus import LinaCorpus, Lina
from dramalyzer import CorpusAnalyzer, DramaAnalyzer


def main(args):
    corpus = CorpusAnalyzer(args.inputfolder, args.outputfolder)
    if args.action == "plotsuperposter":
        plot_superposter(corpus, args.outputfolder, args.debug)
    if args.action == "metrics":
        corpus.get_metrics()
    if args.action == "char_ranks":
        cc = corpus.get_central_characters()
        cc.to_csv(os.path.join(args.outputfolder, "central_characters.csv"), sep=";")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='analyze and plot from lina-xml to networks')
    parser.add_argument('--input', dest='inputfolder', help='relative or absolute path of the input-xmls folder')
    parser.add_argument('--output', dest='outputfolder', help='relative or absolute path of the output folder')
    parser.add_argument('--action', dest='action', help='what to do, either plotsuperposter, metrics, char_ranks')
    parser.add_argument('--debug', dest='debug', help='print debug message or not', action="store_true")
    parser.add_argument('--randomization', dest='random', help='plot randomized graphs', action="store_true")
    args = parser.parse_args()
    main(args)
