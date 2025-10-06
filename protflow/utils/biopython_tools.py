"""
This module provides a collection of utilities for working with BioPython, specifically designed to facilitate the analysis and manipulation of protein structures and sequences. The functionalities included in this module allow users to load, save, and superimpose protein structures from PDB files, as well as extract and analyze sequences from these structures.

Overview
--------
The module encompasses a range of tools to handle various tasks related to protein structural data. Users can load structures from PDB files, save structures back to PDB files, and perform structural superimpositions based on specific atoms or motifs. Additionally, it provides methods to extract sequences from protein structures, renumber residues, and add chains to structures. For sequence analysis, it includes functionalities to load sequences from FASTA files and compute various protein properties using the `Bio.SeqUtils.ProtParam` class.

Examples
--------
Here are some examples of how to use the functions provided in this module:

1. Loading a structure from a PDB file:

    .. code-block:: python

        from biopython_tools import load_structure_from_pdbfile
        structure = load_structure_from_pdbfile("example.pdb")

2. Saving a structure to a PDB file:

    .. code-block:: python

        from biopython_tools import save_structure_to_pdbfile
        save_structure_to_pdbfile(structure, "output.pdb")

3. Superimposing one structure onto another:

    .. code-block:: python

        from biopython_tools import superimpose
        superimposed_structure = superimpose(mobile_structure, target_structure)

4. Extracting sequence from a protein structure:

    .. code-block:: python

        from biopython_tools import get_sequence_from_pose
        sequence = get_sequence_from_pose(structure)

5. Loading a sequence from a FASTA file:

    .. code-block:: python

        from biopython_tools import load_sequence_from_fasta
        sequence_record = load_sequence_from_fasta("example.fasta")

6. Calculating protein parameters from a sequence:

    .. code-block:: python

        from biopython_tools import determine_protparams
        parameters = determine_protparams(sequence_record.seq)

These examples illustrate the primary capabilities of the module, showcasing how it can be utilized to streamline the process of working with protein structures and sequences in BioPython.

Authors
-------
Markus Braun, Adrian Tripp
"""
# Imports
import copy
import os
import string
from typing import Union
import Bio.PDB.Entity
import numpy as np
import pandas as pd

# dependencies
import Bio
import Bio.PDB
from Bio.PDB.Structure import Structure
from Bio.PDB.Model import Model
from Bio import SeqIO
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from Bio.SeqUtils import seq1, seq3
from Bio.PDB import Polypeptide, MMCIFParser
import Bio.PDB.Model
import Bio.PDB.Structure

# customs
from ..residues import ResidueSelection

def load_structure_from_pdbfile(path_to_pdb: str, all_models = False, model: int = 0, quiet: bool = True, handle: str = None) -> Union[Structure, Model]:
    """
    Load a structure from a PDB file using BioPython's PDBParser.

    This function parses a PDB file and returns a structure object. It allows
    the option to load all models from the PDB file or a specific model.

    Parameters:
    -----------
        path_to_pdb (str):
            Path to the PDB file to be parsed.
        all_models (bool, optional):
            If True, all models from the PDB file are returned.
            If False, only the specified model is returned. Defaults to False.
        model (int, optional):
            The index of the model to return. Only used if all_models is False.
            Defaults to 0 (first model).
        quiet (bool, optional):
            If True, suppresses output from the PDBParser. Defaults to True.
        handle (str, optional):
            String handle that is passed to the PDBParser's get_structure()
            method and sets the id of the structure.

    Returns:
    --------
        Bio.PDB.Structure:
            The parsed structure object from the PDB file. If all_models is True,
            returns a Structure containing all models. Otherwise, returns a single
            Model object at the specified index.

    Raises:
    -------
        FileNotFoundError:
            If the specified PDB file does not exist.
        ValueError:
            If the specified model index is out of range for the PDB file.

    Example:
    --------
        To load the first model from a PDB file:
        >>> structure = load_structure_from_pdbfile("example.pdb")

        To load all models from a PDB file:
        >>> all_structures = load_structure_from_pdbfile("example.pdb", all_models=True)
    """
    # sanity
    if not os.path.isfile(path_to_pdb):
        raise FileNotFoundError(f"PDB file {path_to_pdb} not found!")
    if not path_to_pdb.endswith(".pdb"):
        raise ValueError(f"File must be .pdb file. File: {path_to_pdb}")

    # set description as structure name if no other name is provided
    if not handle:
        handle = os.path.splitext(os.path.basename(path_to_pdb))[0]

    # load poses
    pdb_parser = Bio.PDB.PDBParser(QUIET=quiet)
    if all_models:
        return pdb_parser.get_structure(handle, path_to_pdb)
    return pdb_parser.get_structure(handle, path_to_pdb)[model]

def save_structure_to_pdbfile(pose: Structure, save_path: str, multimodel: bool = False) -> None:
    """
    Save a BioPython structure object to a PDB file.

    This function takes a BioPython `Structure` object and writes it to a specified file in PDB format. It is useful for saving modified structures or for converting structures into PDB files for further analysis or visualization.

    Parameters:
    -----------
    pose : Bio.PDB.Structure
        The BioPython `Structure` object to be saved.
    save_path : str
        The file path where the PDB file will be written. The file will be created if it does not exist, or overwritten if it does.
    multimodel : bool
        If the structure to be saved is a multimodel PDB file, write all models. Only works if input is a Structure object, not a model!
    
    Returns:
    --------
    None

    Raises:
    -------
    IOError
        If the file cannot be written to the specified path.

    Example:
    --------
    Save a BioPython structure to a PDB file:

    .. code-block:: python

        from biopython_tools import save_structure_to_pdbfile
        from Bio.PDB import PDBParser

        # Load a structure using BioPython's PDBParser
        parser = PDBParser()
        structure = parser.get_structure("example", "example.pdb")

        # Save the structure to a new PDB file
        save_structure_to_pdbfile(structure, "output.pdb")
    """
    # setup multimodel saving
    if multimodel:
        # sanity and prep PDBIO for multimodel structure
        if not isinstance(pose, Structure):
            raise TypeError(f"Input pose must be a BioPython Structure, not {type(pose)}!")
        for model in pose.get_models():
            model.serial_num = model.id
        io = Bio.PDB.PDBIO(use_model_flag=True)

        # remove existing garbage and store
        if os.path.exists(save_path):
            os.remove(save_path)
        with open(save_path, 'a', encoding="UTF-8") as f:
            io.set_structure(pose)
            io.save(f)

    io = Bio.PDB.PDBIO()
    io.set_structure(pose)
    io.save(save_path)

def get_next_chain_id(existing_ids):
    """
    Generate the next available chain ID for a protein structure.

    Chain IDs are generated as single letters from 'A' to 'Z' and, if all single-letter
    chain IDs are occupied, as double-letter combinations from 'AA' to 'ZZ'.

    Parameters
    ----------
    existing_ids : iterable
        A collection of existing chain IDs to avoid.

    Returns
    -------
    str
        The next available chain ID that is not in `existing_ids`.

    Raises
    ------
    ValueError
        If no available chain IDs are found.
    """
    from itertools import chain, product

    # Generate single-letter chain IDs ('A' to 'Z')
    single_letters = list(string.ascii_uppercase)

    # Generate double-letter chain IDs ('AA', 'AB', ..., 'ZZ')
    double_letters = [''.join(pair) for pair in product(string.ascii_uppercase, repeat=2)]

    # Combine both lists
    all_chain_ids = chain(single_letters, double_letters)

    # Find the first available chain ID
    for chain_id in all_chain_ids:
        if chain_id not in existing_ids:
            return chain_id
    raise ValueError("No available chain IDs.")

def superimpose_on_motif(mobile: Structure, target: Structure, mobile_atoms: ResidueSelection = None, target_atoms: ResidueSelection = None, atom_list: list[str] = None) -> Structure:
    """
    Superimpose a mobile structure onto a target structure based on specified motifs or atom lists.

    This function performs structural superimposition of a mobile protein structure onto a target protein structure. The superimposition can be based on specified motifs or lists of atoms. If no specific atoms are provided, the superimposition is based on the alpha carbon (CA) atoms.

    Parameters:
    -----------
    mobile : Bio.PDB.Structure
        The BioPython `Structure` object representing the mobile structure to be superimposed.
    target : Bio.PDB.Structure
        The BioPython `Structure` object representing the target structure.
    mobile_atoms : ResidueSelection, optional
        A selection of residues from the mobile structure to be used for superimposition. If not provided, defaults to the backbone atoms.
    target_atoms : ResidueSelection, optional
        A selection of residues from the target structure to be used for superimposition. If not provided, defaults to the backbone atoms.
    atom_list : list of str, optional
        A list of atom names to use for the superimposition. If not provided, defaults to ["N", "CA", "O"].

    Returns:
    --------
    Bio.PDB.Structure
        The mobile structure after superimposition onto the target structure.

    Example:
    --------
    Superimpose a mobile structure onto a target structure based on CA atoms:

    .. code-block:: python

        from biopython_tools import superimpose_on_motif, load_structure_from_pdbfile

        # Load structures
        mobile_structure = load_structure_from_pdbfile("mobile.pdb")
        target_structure = load_structure_from_pdbfile("target.pdb")

        # Superimpose mobile structure onto target structure
        superimposed_structure = superimpose_on_motif(mobile_structure, target_structure)

    Notes:
    ------
    - If no specific atoms or motifs are provided, the function defaults to using the backbone atoms (N, CA, O) for superimposition.
    - The superimposed structure is modified in place and returned.
    """
    # prep inputs
    atom_list = atom_list or ["N", "CA", "O"]

    # if no motif is specified, superimpose on protein backbones.
    if (mobile_atoms is None and target_atoms is None):
        mobile_atms = get_atoms(mobile, atoms=atom_list)
        target_atms = get_atoms(target, atoms=atom_list)

    # collect atoms of motif. If only one of the motifs is specified, use the same motif for both target and mobile
    else:
        # in case heavy-atom superimposition is desired, pass 'all' for atom_list
        if atom_list == "all":
            atom_list = None
        mobile_atms = get_atoms_of_motif(mobile, mobile_atoms or target_atoms, atoms=atom_list)
        target_atms = get_atoms_of_motif(target, target_atoms or mobile_atoms, atoms=atom_list)

    # superimpose and return
    super_imposer = Bio.PDB.Superimposer()
    super_imposer.set_atoms(target_atms, mobile_atms)
    super_imposer.apply(mobile)
    return mobile

def superimpose(mobile: Structure, target: Structure, mobile_atoms: list = None, target_atoms: list = None):
    """
    Superimpose a mobile structure onto a target structure based on specified atoms.

    This function performs structural superimposition of a mobile protein structure onto a target protein structure. The superimposition can be based on specified lists of atoms. If no specific atoms are provided, the superimposition is based on the backbone atoms (N, CA, O).

    Parameters:
    -----------
    mobile : Bio.PDB.Structure
        The BioPython `Structure` object representing the mobile structure to be superimposed.
    target : Bio.PDB.Structure
        The BioPython `Structure` object representing the target structure.
    mobile_atoms : list, optional
        A list of atoms from the mobile structure to be used for superimposition. If not provided, defaults to the backbone atoms.
    target_atoms : list, optional
        A list of atoms from the target structure to be used for superimposition. If not provided, defaults to the backbone atoms.

    Returns:
    --------
    Bio.PDB.Structure
        The mobile structure after superimposition onto the target structure.

    Example:
    --------
    Superimpose a mobile structure onto a target structure based on backbone atoms:

    .. code-block:: python

        from biopython_tools import superimpose, load_structure_from_pdbfile

        # Load structures
        mobile_structure = load_structure_from_pdbfile("mobile.pdb")
        target_structure = load_structure_from_pdbfile("target.pdb")

        # Superimpose mobile structure onto target structure
        superimposed_structure = superimpose(mobile_structure, target_structure)

    Notes:
    ------
    - If no specific atoms are provided, the function defaults to using the backbone atoms (N, CA, O) for superimposition.
    - The superimposed structure is modified in place and returned.
    """
    # superimpose on protein Backbones if no atoms are provided
    atom_list = ["N", "CA", "O"]
    if (mobile_atoms is None and target_atoms is None):
        mobile_atoms = get_atoms(mobile, atoms=atom_list)
        target_atoms = get_atoms(target, atoms=atom_list)

    # superimpose and return
    super_imposer = Bio.PDB.Superimposer()
    super_imposer.set_atoms(target_atoms, mobile_atoms)
    super_imposer.apply(mobile)
    return mobile

def get_atoms(structure: Structure, atoms: list[str], chains: list[str] = None, include_het_atoms: bool = False) -> list:
    '''
    Extract specific atoms from one or more chains in a Biopython ``Structure``.

    Parameters:
    -----------
        structure (Bio.PDB.Structure.Structure):
            The input structure that will be searched.
        atoms (list[str]):
            Atom names to extract (e.g. ``["N", "CA", "C", "O"]``).  
            If an empty list or ``None`` is supplied, **all** atoms in each
            selected residue are returned.
        chains (list[str], optional):
            Chain identifiers to restrict the search (e.g. ``["A", "B"]``).  
            When *None* (default), every chain in *structure* is processed.
        include_het_atoms (bool, optional):
            If ``True``, hetero-atoms and ligands are included in addition to
            standard amino-acid residues.  
            Defaults to ``False`` (only ATOM records where ``residue.id[0] == " "``).

    Returns:
    --------
        list[Bio.PDB.Atom.Atom]:
            A list of ``Atom`` objects matching the query, in the order they
            appear in the structure.

    '''
    # Gather all chains from the structure
    chains = [structure[chain] for chain in chains] if chains else [chain for chain in structure]

    # loop over chains and residues and gather all atoms.
    atms_list = []
    for chain in chains:
        # Only select amino acids in each chain:
        residues = [res for res in chain if include_het_atoms or res.id[0] == " "]

        for residue in residues:
            # sort atoms by their atom name, ordering of atoms within residues differs depending on the software creating the .pdb file
            if atoms:
                atms_list += [residue[atom] for atom in atoms]
            else:
                atms_list += sorted(list(residue.get_atoms()), key=lambda a: a.id)

    return atms_list

def get_atoms_of_motif(pose: Structure, motif: ResidueSelection, atoms: list[str] = None, excluded_atoms: list[str] = None, exclude_hydrogens: bool = True, include_het_atoms: bool = False) -> list:
    """
    Select atoms from a structure based on a provided motif.

    This function extracts atoms from a structure based on a specified motif, which is defined by a list of residues. The user can specify which atoms to include or exclude, and whether to exclude hydrogen atoms.

    Parameters:
    -----------
    pose : Bio.PDB.Structure
        The BioPython `Structure` object from which atoms are to be extracted.
    motif : ResidueSelection
        A selection of residues defining the motif from which atoms will be extracted.
    atoms : list of str, optional
        A list of atom names to extract from the residues. If not provided, all atoms in the residues are extracted.
    excluded_atoms : list of str, optional
        A list of atom names to exclude from the extraction. Defaults to ["H", "NE1", "OXT"].
    exclude_hydrogens : bool, optional
        If True, hydrogen atoms are excluded from the extraction. Defaults to True.

    Returns:
    --------
    list
        A list of Bio.PDB.Atom objects corresponding to the specified motif and atom selection.

    Example:
    --------
    Extract CA atoms from a specified motif:

    .. code-block:: python

        from biopython_tools import get_atoms_of_motif, load_structure_from_pdbfile

        # Load structure
        structure = load_structure_from_pdbfile("example.pdb")

        # Define motif (example)
        motif = [("A", 10), ("A", 11), ("A", 12)]

        # Get CA atoms from the motif
        atoms = get_atoms_of_motif(structure, motif, atoms=["CA"])

    Notes:
    ------
    - The function allows for flexibility in defining the selection of atoms based on the motif.
    - If `exclude_hydrogens` is True, hydrogen atoms will not be included in the output list.
    """
    # setup params
    if motif is None:
        return None
    if excluded_atoms is None:
        excluded_atoms = ["H", "NE1", "OXT"] # exclude hydrogens and terminal N and O because they lead to crashes when calculating all-atom RMSD

    # empty list to collect atoms into:
    out_atoms = []
    for chain, res_id in motif:
        if atoms:
            if include_het_atoms: # if this flag is set, only read in atoms of the first residue
                for res in pose[chain].get_residues():
                    if res.id[1] == res_id:
                        res_atoms = [res[atm] for atm in atoms]; break
            else:
                res_atoms = [pose[chain][(" ", res_id, " ")][atom] for atom in atoms]
        else:
            if include_het_atoms: # if this flag is set, only read in atoms of the first residue
                for res in pose[chain].get_residues():
                    if res.id[1] == res_id:
                        res_atoms = sorted(list(res.get_atoms()), key=lambda a: a.id); break
            else:
                res_atoms = sorted(list(pose[chain][(" ", res_id, " ")].get_atoms()), key=lambda a: a.id) # sort atoms, otherwise RMSD is affected by atom ordering. Atom ordering depends on the tool that generated the .pdb file.

        # filter out forbidden atoms
        res_atoms = [atom for atom in res_atoms if atom.name not in excluded_atoms]
        if exclude_hydrogens:
            res_atoms = [atom for atom in res_atoms if atom.element != "H"]

        # add atoms into aggregation list:
        out_atoms += res_atoms
    return out_atoms

def add_chain(target: Structure, reference: Structure, copy_chain: str, translate_x: float = None, overwrite: bool = False) -> Structure:
    """
    Add a chain from a reference structure to a target structure, optionally translating it and handling ID conflicts.

    Parameters
    ----------
    target : Structure
        The structure to which the chain will be added.
    reference : Structure
        The structure from which the chain will be copied.
    copy_chain : str
        The chain ID in the reference structure to be copied.
    translate_x : float, optional
        The distance by which to translate the new chain along the x-axis (default is None).
    overwrite : bool, optional
        Whether to overwrite the chain in the target structure if a chain with the same ID already exists.
        If False and a conflict occurs, a new unique chain ID will be generated (default is True).

    Returns
    -------
    Structure
        The updated target structure with the added chain.
    """
    existing_chain_ids = {chain.id for chain in target.get_chains()}
    new_chain_id = copy_chain

    if copy_chain in existing_chain_ids:
        if overwrite:
            target.detach_child(copy_chain)
        else:
            new_chain_id = get_next_chain_id(existing_chain_ids)

    # Deep copy the chain to avoid modifying the reference structure
    chain_to_add = copy.deepcopy(reference[copy_chain])
    chain_to_add.id = new_chain_id
    target.add(chain_to_add)

    if translate_x:
        translate_entity(target[new_chain_id], vector=np.array([translate_x, 0, 0]))

    return target

def translate_entity(entity: Bio.PDB.Entity, vector: np.array) -> None:
    """
    Translates all atom coordinates in the given entity by the specified vector.

    Parameters:
    -----------
    entity : Bio.PDB.Entity.Entity
        The entity (Structure, Model, Chain, or Residue) whose coordinates will be translated.
    vector : array-like of shape (3,)
        The translation vector (dx, dy, dz).

    Returns:
    --------
    None
        The entity is modified in place.
    
    """
    # Ensure the vector is a NumPy array
    vector = np.array(vector, dtype=float)

    # Collect all atoms in the entity
    atoms = list(entity.get_atoms())

    # Extract all coordinates into a NumPy array
    coords = np.array([atom.get_coord() for atom in atoms])

    # Apply the translation to all coordinates at once
    coords += vector

    # Update the atom coordinates
    for atom, new_coord in zip(atoms, coords):
        atom.set_coord(new_coord)

######################## Bio.PDB.Structure.Structure functions ##########################################
def get_sequence_from_pose(pose: Structure, chain_sep:str=":", with_chains: bool = False) -> str|dict[str,str]:
    '''
    Extracts the sequence of peptides from a protein structure.

    Parameters:
    - pose (Bio.PDB.Structure.Structure): A BioPython Protein Data Bank (PDB) structure object containing the protein's atomic coordinates.
    - chain_sep (str, optional): Separator used to join the sequences of individual peptides. Default is ":".

    Returns:
    - str: The concatenated sequence of peptides, separated by the specified separator.

    Description:
    This function takes a BioPython PDB structure object 'pose' and extracts the sequences of individual peptides within the structure using the PPBuilder from BioPython. It then joins these sequences into a single string, using the 'chain_sep' as a separator. The resulting string represents the concatenated sequence of peptides in the protein structure.

    Example:
    >>> structure = Bio.PDB.PDBParser().get_structure("example", "example.pdb")
    >>> sequence = get_sequence_from_pose(structure, "-")
    >>> print(sequence)
    'MSTHRRRPQEAAGRVNRLPGTPLARAKYFYPKPGERKVEQTPWFAWDVTAGNEYEDTIEFRLEAEGKVGEVVEREDPDNGRGNFARFSLGLYGSKTQYRLPFTVEEVFHDLESVTQKDGFWNCTAFRTVQRLPRTRVAAELNPRAKAAASAVFTFQSQDVDAVANAVEACFAGFYEVVGVFVSNAVDGSVAGAQNFSQFCVGFRGGPRMLRQNRAPATFASAGNHPAKVLAACGLRYAA...
    '''
    if float(Bio.__version__) <= 1.73:
        print(f"WARNING: You are using this function with an unsupported (old) version of BioPython <= 1.73. This might cause your sequences to be extracted wrongly. Your BioPython: {Bio.__version__}")
    # setup PPBuilder:
    ppb = Bio.PDB.PPBuilder()

    # collect sequence
    if with_chains:
        assert isinstance(pose, Model), "pose has to be of type {Model} for this function to work with parameter :with_chains: set:"
        pose = remove_non_residue_residues(model=pose)
        return {chain.id: "".join(str(pept.get_sequence()) for pept in ppb.build_peptides(chain)) for chain in pose.get_chains() if len(list(chain.get_residues())) > 0}
    else:
        return chain_sep.join([str(x.get_sequence()) for x in ppb.build_peptides(pose)])

def renumber_pdb_by_residue_mapping(pose_path: str, residue_mapping: dict, out_pdb_path: str = None, keep_chain: str = "", overwrite: bool = False) -> str:
    """
    Renumber the residues of a BioPython structure based on a residue mapping.

    This function renumbers the residues in a BioPython structure according to a specified mapping. The mapping defines the old and new residue identifiers. The user can choose to keep a specific chain unchanged.

    Parameters:
    -----------
    pose : Bio.PDB.Structure
        The BioPython `Structure` object whose residues will be renumbered.
    residue_mapping : dict
        A dictionary mapping old residue identifiers to new identifiers. Format: {(old_chain, old_id): (new_chain, new_id), ...}.
    keep_chain : str, optional
        The identifier of a chain to keep unchanged. Defaults to an empty string.

    Returns:
    --------
    Bio.PDB.Structure
        The renumbered structure.

    Example:
    --------
    Renumber residues in a structure based on a mapping:

    .. code-block:: python

        from biopython_tools import renumber_pose_by_residue_mapping, load_structure_from_pdbfile

        # Load structure
        structure = load_structure_from_pdbfile("example.pdb")

        # Define residue mapping (example)
        residue_mapping = {("A", 10): ("A", 20), ("A", 11): ("A", 21)}

        # Renumber residues in the structure
        renumbered_structure = renumber_pose_by_residue_mapping(structure, residue_mapping)

    Notes:
    ------
    - The function creates a deep copy of the input structure and applies the residue renumbering to the copy.
    - The `keep_chain` parameter allows for retaining the original numbering of a specified chain.
    """
    path_to_output_structure = out_pdb_path or pose_path

    # check if output already exists
    if not overwrite and os.path.isfile(path_to_output_structure) and out_pdb_path != pose_path:
        return path_to_output_structure

    # change numbering
    pose = load_structure_from_pdbfile(pose_path)
    pose = renumber_pose_by_residue_mapping(pose=pose, residue_mapping=residue_mapping, keep_chain=keep_chain)

    # save pose
    save_structure_to_pdbfile(pose, path_to_output_structure)
    return path_to_output_structure

def renumber_pose_by_residue_mapping(pose: Bio.PDB.Structure.Structure, residue_mapping: dict, keep_chain: str = "") -> Bio.PDB.Structure.Structure:
    """
    Renumber the residues of a BioPython structure based on a residue mapping.

    This function renumbers the residues in a BioPython structure according to a specified mapping. The mapping defines the old and new residue identifiers. The user can choose to keep a specific chain unchanged.

    Parameters:
    -----------
    pose : Bio.PDB.Structure
        The BioPython `Structure` object whose residues will be renumbered.
    residue_mapping : dict
        A dictionary mapping old residue identifiers to new identifiers. Format: {(old_chain, old_id): (new_chain, new_id), ...}.
    keep_chain : str, optional
        The identifier of a chain to keep unchanged. Defaults to an empty string.

    Returns:
    --------
    Bio.PDB.Structure
        The renumbered structure.

    Example:
    --------
    Renumber residues in a structure based on a mapping:

    .. code-block:: python

        from biopython_tools import renumber_pose_by_residue_mapping, load_structure_from_pdbfile

        # Load structure
        structure = load_structure_from_pdbfile("example.pdb")

        # Define residue mapping (example)
        residue_mapping = {("A", 10): ("A", 20), ("A", 11): ("A", 21)}

        # Renumber residues in the structure
        renumbered_structure = renumber_pose_by_residue_mapping(structure, residue_mapping)

    Notes:
    ------
    - The function creates a deep copy of the input structure and applies the residue renumbering to the copy.
    - The `keep_chain` parameter allows for retaining the original numbering of a specified chain.
    """
    # deepcopy pose and detach all residues from chains
    out_pose = copy.deepcopy(pose)
    ch = [chain.id for chain in out_pose.get_chains() if chain.id != keep_chain]

    # remove all residues from old chains:
    for chain in ch:
        residues = [res.id for res in out_pose[chain].get_residues()]
        for resi in residues:
            out_pose[chain].detach_child(resi)

    # collect residues with renumbered ids and chains into one list:
    for (old_chain, old_id), (new_chain, new_id) in residue_mapping.items():
        # remove old residue from original pose
        res = pose[old_chain][(" ", old_id, " ")]
        pose[old_chain].detach_child((" ", old_id, " "))
        res.detach_parent()

        # set new residue ID
        res.id = (" ", new_id, " ")

        # add to appropriate chain (residue mapping) in out_pose
        out_pose[new_chain].add(res)

    # remove chains from pose that are empty:
    chain_ids = [x.id for x in out_pose] # for some reason, iterating over chains in struct directly does not work here...
    for chain_id in chain_ids:
        if not out_pose[chain_id].__dict__["child_dict"]:
            out_pose.detach_child(chain_id)

    return out_pose

######################## Bio.Seq functions ##########################################
def load_sequence_from_fasta(fasta:str, return_multiple_entries:bool=True):
    """
    Load a sequence from a FASTA file.

    This function imports a FASTA file and returns a sequence record or a record iterator depending on the number of entries and the specified options.

    Parameters:
    -----------
    fasta : str
        Path to the FASTA file to be imported.
    return_multiple_entries : bool, optional
        If True, returns a record iterator for multiple entries. If False, returns a single record even if the file contains multiple entries. Defaults to True.

    Returns:
    --------
    Bio.SeqRecord.SeqRecord or iterator
        A single `SeqRecord` object if the file contains one entry or `return_multiple_entries` is False. Otherwise, a record iterator for multiple entries.

    Example:
    --------
    Load a sequence from a single-entry FASTA file:

    .. code-block:: python

        from biopython_tools import load_sequence_from_fasta

        # Load sequence from FASTA file
        sequence_record = load_sequence_from_fasta("example.fasta")

    Load sequences from a multi-entry FASTA file:

    .. code-block:: python

        from biopython_tools import load_sequence_from_fasta

        # Load sequences from multi-entry FASTA file
        sequence_iterator = load_sequence_from_fasta("multi_example.fasta")

    Notes:
    ------
    - The function utilizes `Bio.SeqIO.parse` to read the FASTA file and determine the number of entries.
    - If `return_multiple_entries` is set to True and the file contains multiple entries, an iterator is returned to handle the sequences.
    """
    records = list(SeqIO.parse(fasta, "fasta"))
    if len(records) == 1 or not return_multiple_entries:
        return records[0]
    return records


def determine_protparams(seq: Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq], pH: float = 7) -> pd.DataFrame:
    """
    Calculate protein features based on a sequence.

    This function calculates various protein properties from an input sequence using BioPython's `Bio.SeqUtils.ProtParam` class. The results are returned in a pandas DataFrame.

    Parameters:
    -----------
    seq : Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq]
        The input sequence for which the protein properties will be calculated. The input can be a string, `SeqRecord`, or `Seq` object.
    pH : float, optional
        The pH value at which to calculate the protein's charge. Defaults to 7.

    Returns:
    --------
    pandas.DataFrame
        A DataFrame containing the calculated protein properties, including molecular weight, aromaticity, GRAVY, isoelectric point, molar extinction coefficients, flexibility, secondary structure fraction, and charge at the specified pH.

    Example:
    --------
    Calculate protein properties for a given sequence:

    .. code-block:: python

        from biopython_tools import determine_protparams
        from Bio.Seq import Seq

        # Define a protein sequence
        sequence = Seq("MSTHRRRPQEAAGRVNRLPGTPLARAKYFYPKPGERKVEQTPWFAWDVTAGNEYEDTIEFRLEAEGKVGEVVEREDPDNGRGNFARFSLGLYGSKTQYRLPFTVEEVFHDLESVTQKDGFWNCTAFRTVQRLPRTRVAAELNPRAKAAASAVFTFQSQDVDAVANAVEACFAGFYEVVGVFVSNAVDGSVAGAQNFSQFCVGFRGGPRMLRQNRAPATFASAGNHPAKVLAACGLRYAA")

        # Calculate properties
        properties_df = determine_protparams(sequence)

        # Print properties
        print(properties_df)

    Notes:
    ------
    - The function supports input sequences in various formats, including strings, `SeqRecord`, and `Seq` objects.
    - The calculated properties include:
        - Molecular weight
        - Aromaticity
        - GRAVY (Grand Average of Hydropathy)
        - Isoelectric point
        - Molar extinction coefficient (reduced and oxidized cysteines)
        - Flexibility
        - Secondary structure fraction (helix, turn, sheet)
        - Charge at the specified pH
    - The function raises a `TypeError` if the input sequence is not in a recognized format.
    """
    # check which type of input is used
    if isinstance(seq, Bio.SeqRecord.SeqRecord):
        seq = seq.seq
    elif isinstance(seq, Bio.Seq.Seq):
        seq = seq.data
    elif isinstance(seq, str):
        pass
    else:
        raise TypeError(f"Input must be a sequence, not {type(seq)}!")

    # analyze sequence
    protparams = ProteinAnalysis(seq)

    # create data dict
    data = {
        "sequence": [seq],
        "molecular_weight": [round(protparams.molecular_weight(), 3)],
        "aromaticity": [round(protparams.aromaticity(), 4)],
        "GRAVY": [round(protparams.gravy(), 4)],
        "instability_index": [protparams.instability_index()],
        "isoelectric_point": [round(protparams.isoelectric_point(), 2)],
        "molar_extinction_coefficient_red": [protparams.molar_extinction_coefficient()[0]],
        "molar_extinction_coefficient_ox": [protparams.molar_extinction_coefficient()[1]],
        "secondary_structure_fraction": [protparams.secondary_structure_fraction()],
        f"charge_at_pH_{pH}": [round(protparams.charge_at_pH(pH=pH), 2)]
    }

    return pd.DataFrame(data)

def three_to_one_AA_code(seq: Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq], custom_map: dict = None, undef_code="X") -> str:
    """
    Converts a sequence in 3-letter code to 1-letter code.

    This function converts an input sequence in 3-letter code to 1-letter code using BioPython's `Bio.SeqUtils` functions. The results are returned in a string.

    Parameters:
    -----------
    seq : Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq]
        The input sequence in 3-letter code. The input can be a string, `SeqRecord`, or `Seq` object.
    custom_map : dict, optional
        Use a custom 1-letter code for a given 3-letter code (e.g. for noncanonical residues).
    undef_code: str, optional
        Replace all unknown 3-letter codes (e.g. from ligands or noncannonical residues) with this string.

    Returns:
    --------
    str
        A string of all residues in the sequence in one-letter code

    Example:
    --------
    Convert 3-letter code to 1-letter code:

    .. code-block:: python

        from biopython_tools import three_to_one_AA_code

        # Define a protein sequence
        sequence = "HisAlaTrp")

        # Calculate properties
        oneletter_seq = three_to_one_AA_code(sequence)

        # Print properties
        print(oneletter_seq)

    Notes:
    ------
    - The function supports input sequences in various formats, including strings, `SeqRecord`, and `Seq` objects.
    """
    return seq1(seq, custom_map=custom_map, undef_code=undef_code)

def one_to_three_AA_code(seq: Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq], custom_map: dict = None, undef_code="X") -> str:
    """
    Converts a sequence in 1-letter code to 3-letter code.

    This function converts an input sequence in 1-letter code to 3-letter code using BioPython's `Bio.SeqUtils` functions. The results are returned in a string.

    Parameters:
    -----------
    seq : Union[str, Bio.SeqRecord.SeqRecord, Bio.Seq.Seq]
        The input sequence in 1-letter code. The input can be a string, `SeqRecord`, or `Seq` object.
    custom_map : dict, optional
        Use a custom 3-letter code for a given 1-letter code (e.g. for noncanonical residues).
    undef_code: str, optional
        Replace all unknown 1-letter codes (e.g. from ligands or noncannonical residues) with this string.

    Returns:
    --------
    str
        A string of all residues in the sequence in one-letter code

    Example:
    --------
    Convert 1-letter code to 3-letter code:

    .. code-block:: python

        from biopython_tools import one_to_three_AA_code

        # Define a protein sequence
        sequence = "HAW")

        # Calculate properties
        threeletter_seq = one_to_three_AA_code(sequence)

        # Print properties
        print(threeletter_seq)

    Notes:
    ------
    - The function supports input sequences in various formats, including strings, `SeqRecord`, and `Seq` objects.
    """
    return seq3(seq, custom_map=custom_map, undef_code=undef_code)

def remove_non_residue_residues(model: Model, remove_hydrogens: bool = False) -> Model:
    """
    Removes non-residue residues from a BioPython Model object,
    keeping only standard amino acids and modified amino acids.
    """
    for residue in model.get_residues():
        residues_to_remove = []
        # Check if residue is a standard amino acid or a modified amino acid
        # by checking if it has a standard three-letter amino acid code.
        if not Polypeptide.is_aa(residue, standard=False):
            residues_to_remove.append(residue)

        # Remove marked residues
        for residue in residues_to_remove:
            residue.get_parent().detach_child(residue.id)

        if remove_hydrogens:
            for atom in residue.get_atoms():
                if atom.element == "H":
                    atom.get_parent().detach_child(atom.id)

    return model

def biopython_load_protein(protein_path: str, model_id: int = None, handle: str = "structure", file_type: str = None) -> Structure|Model:
    """TODO: write proper docstring!
    Loads proteins into biopython Structure/Model objects, irrespective of .pdb or .cif format.
    :file_type: parameter allows to specify explicity which loader should be used. can be {'cif', 'pdb', None}
    """
    # sanitation
    if file_type is None:
        file_type = os.path.splitext(protein_path)[-1]

    match file_type.lower():
        case "pdb" | ".pdb":
            file_type = "pdb"
        case "cif" | "mmcif" | ".cif" | ".mmcif":
            file_type = "cif"
        case _:
            raise ValueError(f":file_type: must be either of {{'cif', 'pdb'}}. Your :file_type: {file_type}")            

    if not os.path.isfile(protein_path):
        raise FileNotFoundError(protein_path)

    # handle .pdb files
    if (protein_path.endswith(".pdb") or file_type.lower() == "pdb") and not file_type.lower() == "cif":
        protein = load_structure_from_pdbfile(
            path_to_pdb=protein_path,
            all_models=model_id is None,
            model=model_id,
            handle=handle
        )
        return protein

    # handle .cif files
    if protein_path.endswith(".cif") or file_type.lower() == "cif":
        # load mmcif
        parser = MMCIFParser()
        protein = parser.get_structure(handle, protein_path)

        # extract model if specified
        if model_id:
            protein = protein[model_id]
        return protein
