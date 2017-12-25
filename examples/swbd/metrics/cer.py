#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Define evaluation method by Character Error Rate (Switchboard corpus)."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tqdm import tqdm

from utils.io.labels.character import Idx2char
from utils.evaluation.edit_distance import compute_cer, compute_wer, wer_align
from examples.swbd.metrics.glm import GLM
from examples.swbd.metrics.post_processing import fix_trans


def do_eval_cer(model, model_type, dataset, label_type, beam_width,
                max_decode_length, eval_batch_size=None, progressbar=False):
    """Evaluate trained model by Character Error Rate.
    Args:
        model: the model to evaluate
        model_type (string): ctc or attention or hierarchical_ctc or
            hierarchical_attention
        dataset: An instance of a `Dataset' class
        label_type (string): character or character_capital_divide
        beam_width: (int): the size of beam
        max_decode_length (int): the length of output sequences
            to stop prediction when EOS token have not been emitted.
            This is used for seq2seq models.
        eval_batch_size (int, optional): the batch size when evaluating the model
        progressbar (bool, optional): if True, visualize the progressbar
    Returns:
        cer_mean (float): An average of CER
        wer_mean (float): An average of WER
    """
    batch_size_original = dataset.batch_size

    # Reset data counter
    dataset.reset()

    # Set batch size in the evaluation
    if eval_batch_size is not None:
        dataset.batch_size = eval_batch_size

    if label_type == 'character':
        idx2char = Idx2char(
            vocab_file_path='../metrics/vocab_files/character_' + dataset.data_size + '.txt')
    elif label_type == 'character_capital_divide':
        idx2char = Idx2char(
            vocab_file_path='../metrics/vocab_files/character_capital_divide_' +
            dataset.data_size + '.txt',
            capital_divide=True)

    # Read GLM file
    glm = GLM(
        glm_path='/n/sd8/inaguma/corpus/swbd/data/eval2000/LDC2002T43/reference/en20000405_hub5.glm')

    cer_mean, wer_mean = 0, 0
    skip_utt_num = 0
    if progressbar:
        pbar = tqdm(total=len(dataset))
    for batch, is_new_epoch in dataset:

        if model_type in ['ctc', 'attention']:
            inputs, labels, inputs_seq_len, labels_seq_len, _ = batch
        elif model_type in ['hierarchical_ctc', 'hierarchical_attention']:
            inputs, _, labels, inputs_seq_len, _, labels_seq_len, _ = batch

        # Decode
        if model_type in ['attention', 'ctc']:
            labels_pred = model.decode(inputs, inputs_seq_len,
                                       beam_width=beam_width,
                                       max_decode_length=max_decode_length)
        elif model_type in['hierarchical_attention', 'hierarchical_ctc']:
            labels_pred = model.decode(inputs, inputs_seq_len,
                                       beam_width=beam_width,
                                       max_decode_length=max_decode_length,
                                       is_sub_task=True)

        for i_batch in range(inputs.shape[0]):

            ##############################
            # Reference
            ##############################
            if dataset.is_test:
                str_true = labels[i_batch][0]
                # NOTE: transcript is seperated by space('_')
            else:
                # Convert from list of index to string
                if model_type in ['ctc', 'hierarchical_ctc']:
                    str_true = idx2char(
                        labels[i_batch][:labels_seq_len[i_batch]])
                elif model_type in ['attention', 'hierarchical_attention']:
                    str_true = idx2char(
                        labels[i_batch][1:labels_seq_len[i_batch] - 1])
                    # NOTE: Exclude <SOS> and <EOS>

            ##############################
            # Hypothesis
            ##############################
            str_pred = idx2char(labels_pred[i_batch])
            if model_type in ['attention', 'hierarchical_attention']:
                str_pred = str_pred.split('>')[0]
                # NOTE: Trancate by the first <EOS>

                # Remove the last space
                if len(str_pred) > 0 and str_pred[-1] == '_':
                    str_pred = str_pred[:-1]

            ##############################
            # Post-proccessing
            ##############################
            str_true = fix_trans(str_true, glm)
            str_pred = fix_trans(str_pred, glm)

            # print('\n' + str_true)
            # print(str_pred)

            word_list_true = str_true.split('_')
            word_list_pred = str_pred.split('_')

            # Compute WER
            if len(str_true) > 0:
                wer_mean += compute_wer(ref=word_list_true,
                                        hyp=word_list_pred,
                                        normalize=True)
                # if len(str_pred) > 0:
                #     substitute, insert, delete = wer_align(
                #         ref=word_list_true,
                #         hyp=word_list_pred)
                #     print('SUB: %d' % substitute)
                #     print('INS: %d' % insert)
                #     print('DEL: %d' % delete)

                # Compute CER
                cer_mean += compute_cer(ref='_'.join(word_list_true),
                                        hyp='_'.join(word_list_pred),
                                        normalize=True)
            else:
                skip_utt_num += 1

            if progressbar:
                pbar.update(1)

        if is_new_epoch:
            break

    if progressbar:
        pbar.close()

    cer_mean /= (len(dataset) - skip_utt_num)
    wer_mean /= (len(dataset) - skip_utt_num)

    # Register original batch size
    if eval_batch_size is not None:
        dataset.batch_size = batch_size_original

    return cer_mean, wer_mean