source activate icu-benchmark
python -m icu_benchmarks.run train \
                             -c configs/hirid/Classification/LocalTransformer.gin \
                             -l logs/hirid/ablation/Horizon/LocalTransformer/ \
                             -t Dynamic_RespFailure_12Hours\
                             -o True \
                             -lr 1e-4\
                             -bs 8\
                             --hidden 128 \
                             --do 0.3 \
                             --do_att 0.2 \
                             --depth 1 \
                             --heads 1 \
                             --horizon 12 36 72 144 288 576 1152 2016 \
                             -sd 1111 2222 3333 4444 5555 \
