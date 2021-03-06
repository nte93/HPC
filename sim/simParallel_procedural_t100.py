import sys
import time
import random
import numpy as np
from array import *
from math import ceil, floor, sqrt
from mpi4py import MPI

comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()

random.seed(rank)

N = 64
t = 3000

if len(sys.argv) > 1:
	N = int(sys.argv[1])

if len(sys.argv) > 2:
	t = int(sys.argv[2])

#height of each partition
height = int(N/size)

#used later (larger scope for speed)
state = 0
index = 0

evenGrid = np.zeros((height, N), dtype=int, order='C')
oddGrid = np.zeros((height, N), dtype=int, order='C')

top_halo = np.zeros(N, dtype=int, order='C')
bot_halo = np.zeros(N, dtype=int, order='C')


#rules defined here
#lots of hard-coding
def new_state(state, index):
	if state == 0:
		if random.randint(1, 501) < 2:
			return 2
		elif index < 6:
			return 0
		elif index < 17:
			return 1
		else:
			return 3

	elif state == 1:
		if random.randint(1, 501) < 2 or index > 16:
			return 3
		elif index < 1:
			return 0
		else:
			return 1
		
	elif state == 2:
		if index > 20:
			return 3
		else:
			return random.choice([2,2,1,1,0])
		

	else:
		if index < 10:
			return 1
		else:
			return 3


def update(timestep):
	
	#step 1: send appropriate rows
	up_dest = int(rank - 1) % int(size)
	down_dest = int(rank + 1) % int(size)

	if timestep % 2 == 0:
		comm.Isend(evenGrid[0, :], dest=up_dest)
		comm.Isend(evenGrid[height - 1, :], dest=down_dest) 
	else:	
		comm.Isend(oddGrid[0, :], dest=up_dest)
		comm.Isend(oddGrid[height - 1, :], dest=down_dest)

	#receive top and bottom extension rows
	req_up = comm.Irecv(top_halo, source=up_dest)
	req_down = comm.Irecv(bot_halo, source=down_dest)

	#for each lattice point NOT on edge, do an update
	for i in range(1, height - 1):
		for j in range(N):

			#index calculation
			index = 0
			if timestep % 2 == 0:
				index += evenGrid[i - 1, j] 
				index += evenGrid[i + 1, j]
				index += evenGrid[i, (j + 1) % N] 
				index += evenGrid[i, (j - 1) % N] 
				index += evenGrid[i - 1, (j + 1) % N]
				index += evenGrid[i + 1, (j - 1) % N] 
				index += evenGrid[i + 1, (j + 1) % N] 
				index += evenGrid[i - 1, (j - 1) % N] 
			else:
				index += oddGrid[i - 1, j] 
				index += oddGrid[i + 1, j]
				index += oddGrid[i, (j + 1) % N]
				index += oddGrid[i, (j - 1) % N] 
				index += oddGrid[(i - 1), (j + 1) % N] 
				index += oddGrid[(i + 1), (j - 1) % N] 
				index += oddGrid[(i + 1), (j + 1) % N] 
				index += oddGrid[(i - 1), (j - 1) % N] 
 			
			#state choices based on index and random number
			if timestep % 2 == 0:
				state = evenGrid[i, j]
			else:
				state = oddGrid[i, j]

			state = new_state(state, index)			

			#update future grid (depends on which timestep)
			if timestep % 2 == 0:
				oddGrid[i, j] = state
			else:
				evenGrid[i, j] = state

	req_up.Wait()
	req_down.Wait()

	#top update calculations
	for j in range(N):
		if timestep % 2 == 0:
			state = evenGrid[0, j]
		else:
			state = oddGrid[0, j]
	
		index = 0

		index += top_halo[(j-1) % N]
		index += top_halo[j]
		index += top_halo[(j+1) % N]

		if timestep % 2 == 0:
			index += evenGrid[0, (j+1) % N]
			index += evenGrid[0, (j-1) % N]
			index += evenGrid[1, (j-1) % N]
			index += evenGrid[1, j]
			index += evenGrid[1, (j+1) % N]
			
		else:
			index += oddGrid[0, (j-1) % N]
			index += oddGrid[0, (j+1) % N]
			index += oddGrid[1, (j-1) % N]
			index += oddGrid[1, j]
			index += oddGrid[1, (j+1) % N]

		state = new_state(state, index)

		if timestep % 2 == 0:
			oddGrid[0, j] = state
		else:
			evenGrid[0, j] = state

	#bottom update calculations
	for j in range(N):
		if timestep % 2 == 0:
			state = evenGrid[height - 1, j]
		else:
			state = oddGrid[height - 1, j]
	
		index = 0
		index += bot_halo[(j-1) % N]
		index += bot_halo[j]
		index += bot_halo[(j+1) % N]

		if timestep % 2 == 0:
			index += evenGrid[height - 1, (j+1) % N]
			index += evenGrid[height - 1, (j-1) % N]
			index += evenGrid[height - 2, (j-1) % N]
			index += evenGrid[height - 2, j]
			index += evenGrid[height - 2, (j+1) % N]
			
		else:
			index += oddGrid[height - 1, (j-1) % N]
			index += oddGrid[height - 1, (j+1) % N]
			index += oddGrid[height - 2, (j-1) % N]
			index += oddGrid[height - 2, j]
			index += oddGrid[height - 2, (j+1) % N]

		state = new_state(state, index)

		if timestep % 2 == 0:
			oddGrid[height-1, j] = state
		else:
			evenGrid[height-1, j] = state


#Writes to a binary data entry file
def write_to_file(most_recent_timestep):
	amode = MPI.MODE_WRONLY|MPI.MODE_CREATE
	output = MPI.File.Open(comm, "./data/end" + str(most_recent_timestep) + ".fbgm", amode)
	if most_recent_timestep % 2 == 0:
		offset = oddGrid.nbytes * rank
		output.Write_at_all(offset, oddGrid)
	else:
		offset = evenGrid.nbytes * rank
		output.Write_at_all(offset, evenGrid)
	output.Close() 
	#thank you donald christopher jones ^

#storing headers
if rank == 0:
	f = open('conditions.fbgm', 'w')
	s = str(N)+"\n"+str(t)+"\n"+str(size)+"\n"+str(height)+"\n"
	f.write(s)
	f.close()

for timestep in range(1, t+1):
	update(timestep)
	if timestep % 100 == 0:
		write_to_file(timestep)
		if rank == 0:
			print("printing step " + str(timestep))
	comm.barrier()


