"""Evaluation utils."""
import sys

sys.path.append('/u/subramas/Research/nmt-pytorch')

import torch
import torch.nn.functional as F
from torch.autograd import Variable
from data_utils import get_minibatch
from collections import Counter
import math
import numpy as np


def bleu_stats(hypothesis, reference):
    """Compute statistics for BLEU."""
    stats = []
    stats.append(len(hypothesis))
    stats.append(len(reference))
    for n in xrange(1, 5):
        s_ngrams = Counter(
            [tuple(hypothesis[i:i + n]) for i in xrange(len(hypothesis) + 1 - n)]
        )
        r_ngrams = Counter(
            [tuple(reference[i:i + n]) for i in xrange(len(reference) + 1 - n)]
        )
        stats.append(max([sum((s_ngrams & r_ngrams).values()), 0]))
        stats.append(max([len(hypothesis) + 1 - n, 0]))
    return stats


def bleu(stats):
    """Compute BLEU given n-gram statistics."""
    if len(filter(lambda x: x == 0, stats)) > 0:
        return 0
    (c, r) = stats[:2]
    log_bleu_prec = sum(
        [math.log(float(x) / y) for x, y in zip(stats[2::2], stats[3::2])]
    ) / 4.
    return math.exp(min([0, 1 - float(r) / c]) + log_bleu_prec)


def get_bleu(hypotheses, reference):
    """Get validation BLEU score for dev set."""
    stats = np.array([0., 0., 0., 0., 0., 0., 0., 0., 0., 0.])
    for hyp, ref in zip(hypotheses, reference):
        stats += np.array(bleu_stats(hyp, ref))
    return 100 * bleu(stats)


def compute_accuracy(preds, ground_truths):
    """Compute prediction accuracy."""
    equal = 0.
    for pred, gold in zip(preds, ground_truths):
        pred = ' '.join(pred)
        gold = ' '.join(gold)
        if pred == gold:
            equal += 1

    return (equal / len(preds)) * 100


def evaluate(
    model, src, src_test, trg,
    trg_test, config, verbose=True,
    metric='accuracy'
):
    """Evaluate model."""
    preds = []
    ground_truths = []
    for j in xrange(0, len(src_test['data']), config['data']['batch_size']):

        input_lines_src, output_lines_src, lens_src, mask_src = get_minibatch(
            src_test['data'], src['word2id'], j, config['data']['batch_size'],
            config['data']['max_src_length'], add_start=True, add_end=True
        )

        input_lines_trg_gold, output_lines_trg_gold, lens_src, mask_src = get_minibatch(
            trg_test['data'], trg['word2id'], j, config['data']['batch_size'],
            config['data']['max_src_length'], add_start=True, add_end=True
        )

        input_lines_trg = Variable(torch.LongTensor(
            [
                [trg['word2id']['<s>']]
                for i in xrange(config['data']['batch_size'])
            ]
        )).cuda()

        if input_lines_src.size()[0] != config['data']['batch_size']:
            break

        for i in xrange(config['data']['max_src_length']):
            decoder_logit = model(input_lines_src, input_lines_trg)
            logits_reshape = decoder_logit.view(-1, len(trg['word2id']))
            word_probs = F.softmax(logits_reshape)
            word_probs = word_probs.view(
                decoder_logit.size()[0],
                decoder_logit.size()[1],
                decoder_logit.size()[2]
            )
            decoder_argmax = word_probs.data.cpu().numpy().argmax(axis=-1)
            next_preds = Variable(
                torch.from_numpy(decoder_argmax[:, -1])
            ).cuda()

            input_lines_trg = torch.cat(
                (input_lines_trg, next_preds.unsqueeze(1)),
                1
            )

        input_lines_trg = input_lines_trg.data.cpu().numpy()
        input_lines_trg = [
            [trg['id2word'][x] for x in line]
            for line in input_lines_trg
        ]

        output_lines_trg_gold = output_lines_trg_gold.data.cpu().numpy()
        output_lines_trg_gold = [
            [trg['id2word'][x] for x in line]
            for line in output_lines_trg_gold
        ]

        for sentence_pred, sentence_real, sentence_real_src in zip(
            input_lines_trg,
            output_lines_trg_gold,
            output_lines_src
        ):
            if '</s>' in sentence_pred:
                index = sentence_pred.index('</s>')
            else:
                index = len(sentence_pred)
            preds.append(sentence_pred[1:index])

            if verbose:
                print ' '.join(sentence_pred[1:index])

            if '</s>' in sentence_real:
                index = sentence_real.index('</s>')
            else:
                index = len(sentence_real)
            if verbose:
                print ' '.join(sentence_real[:index])
            if verbose:
                print '--------------------------------------'
            ground_truths.append(sentence_real[:index])

            if '</s>' in sentence_real_src:
                index = sentence_real_src.index('</s>')
            else:
                index = len(sentence_real_src)

    if metric == 'accuracy':
        return compute_accuracy(preds, ground_truths)
    else:
        return bleu(preds, ground_truths)
