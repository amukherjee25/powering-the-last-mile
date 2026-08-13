#!/bin/bash
#SBATCH --job-name=district_block_pv_sizing
#SBATCH --array=0-21                    # Indexes for different blocks
#SBATCH -c 1                            # Number of Cores per Task
#SBATCH --mem=5G                        # Requested Memory (5 GB)
#SBATCH -p cpu                          # Partition
#SBATCH --gpus=0                        # Number of GPUs
#SBATCH -t 2-00:00:00                   # Job time limit (2 days)
#SBATCH --mail-type=ALL,TIME_LIMIT_80   # Email notifications (BEGIN, END, FAIL, etc.) and when job is 80% complete
#SBATCH --mail-user=ahanam@uw.edu       # Notifications will be sent to the following email address
#SBATCH -o slurm-%A_%a.out              # Job array output (%A = master job ID, %a = array task ID)
#SBATCH --output=logs/output_%A_%a.log
#SBATCH --error=logs/error_%A_%a.log

# Load the Conda module
module load conda/latest

# Activate the Conda environment
conda activate /work/pi_jtaneja_umass_edu/ahanamukherj_umass_edu/envs/pv_sizing_env

# Read the block and district using a delimiter-safe method
LINE=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" district_blocks.txt)
BLOCK=$(echo "$LINE" | cut -d'|' -f1 | xargs)       # Strip any leading/trailing whitespaces; use the | delimiter to separate block and district names
DISTRICT=$(echo "$LINE" | cut -d'|' -f2 | xargs)    # Strip any leading/trailing whitespaces; use the | delimiter to separate block and district names

# Run the script
python3 run_pv_sizing_block.py "$BLOCK" "$DISTRICT"