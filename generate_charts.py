import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

os.makedirs('results_figures', exist_ok=True)

# Set style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.size'] = 11

# 1. Gaming Benchmark (Latency & Jitter)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
labels = ['Avg Latency (ms)', 'TCP Connect (ms)']
before = [18.24, 18.92]
after = [17.30, 19.82]
x = np.arange(len(labels))
width = 0.35

rects1 = ax1.bar(x - width/2, before, width, label='Before (CUBIC/pfifo)', color='#94a3b8')
rects2 = ax1.bar(x + width/2, after, width, label='After (BBR/fq_codel)', color='#2563eb')
ax1.set_ylabel('Milliseconds (ms)')
ax1.set_title('Ping & Handshake Latency')
ax1.set_xticks(x)
ax1.set_xticklabels(labels)
ax1.legend(loc='upper right')
ax1.bar_label(rects1, padding=3, fmt='%.1f')
ax1.bar_label(rects2, padding=3, fmt='%.1f')

# Jitter bar
jitter_labels = ['Jitter / mdev (ms)']
jb = [2.21]
ja = [1.40]
xj = np.arange(len(jitter_labels))
rectsj1 = ax2.bar(xj - width/2, jb, width, label='Before', color='#94a3b8')
rectsj2 = ax2.bar(xj + width/2, ja, width, label='After (Tuned)', color='#10b981')
ax2.set_ylabel('Milliseconds (ms)')
ax2.set_title('Ping Jitter (36.6% Reduction)')
ax2.set_xticks(xj)
ax2.set_xticklabels(jitter_labels)
ax2.bar_label(rectsj1, padding=3, fmt='%.2f')
ax2.bar_label(rectsj2, padding=3, fmt='%.2f')
ax2.text(0, 1.8, '▲ 36.6% Jitter Improvement\n(Bufferbloat Elimination)', ha='center', color='#047857', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#d1fae5', edgecolor='#10b981'))

plt.tight_layout()
plt.savefig('results_figures/gaming_benchmark.png', dpi=200)
plt.close()

# 2. Streaming & Broadcasting Throughput
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

# Streaming
s_labels = ['Receiver Throughput']
s_before = [20575.6]
s_after = [30164.7]
xs = np.arange(len(s_labels))
sr1 = ax1.bar(xs - width/2, s_before, width, label='Before (Default 208KB)', color='#94a3b8')
sr2 = ax1.bar(xs + width/2, s_after, width, label='After (16MB Window)', color='#8b5cf6')
ax1.set_ylabel('Throughput (Mbps)')
ax1.set_title('Streaming Workload (iperf3 -R)')
ax1.set_xticks(xs)
ax1.set_xticklabels(s_labels)
ax1.bar_label(sr1, padding=3, fmt='%.0f')
ax1.bar_label(sr2, padding=3, fmt='%.0f')
ax1.text(0, 26000, '+46.6% Bandwidth\n(16 MB rwnd autotune)', ha='center', color='#6d28d9', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#ede9fe', edgecolor='#8b5cf6'))

# Broadcasting
b_labels = ['Sender Upload Throughput']
b_before = [18364.3]
b_after = [21585.9]
xb = np.arange(len(b_labels))
br1 = ax2.bar(xb - width/2, b_before, width, label='Before (Default)', color='#94a3b8')
br2 = ax2.bar(xb + width/2, b_after, width, label='After (BBR + FQ)', color='#f59e0b')
ax2.set_ylabel('Throughput (Mbps)')
ax2.set_title('Broadcasting Workload (iperf3)')
ax2.set_xticks(xb)
ax2.set_xticklabels(b_labels)
ax2.bar_label(br1, padding=3, fmt='%.0f')
ax2.bar_label(br2, padding=3, fmt='%.0f')
ax2.text(0, 19800, '+17.5% Paced Upload\n(BBR Pacing & wmem)', ha='center', color='#b45309', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#fef3c7', edgecolor='#f59e0b'))

plt.tight_layout()
plt.savefig('results_figures/throughput_benchmarks.png', dpi=200)
plt.close()

print('Charts generated successfully.')
