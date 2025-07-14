import yaml
import json
import logging

logger = logging.getLogger(__name__)


def generic_yaml_to_json(
    filepath: str,
    output_path: str,
    id_key: str,
    fixed_keys: list[str],
    list_keys: list[str],
    group_id_from: str = None,  # 用于从其他字段取 SkillIdLv 等
    logger_prefix: str = ""
):
    logger.debug(f"{logger_prefix}Loading from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a list in {filepath}, but got {type(data)}")

        result_dict = {}
        unit = {}
        LastEffectNo = "1"
        LastSkillIdLv = 0
        for entry in data:
            try:
                NewEffectNo = str(entry[id_key])[-1]
                SkillIdLv = int(str(entry[group_id_from or id_key])[0:10])
                if NewEffectNo <= LastEffectNo:
                    result_dict[LastSkillIdLv] = unit
                    LastSkillIdLv = SkillIdLv
                    unit = {key: entry[key] for key in fixed_keys}
                    for lk in list_keys:
                        unit[lk] = [entry[lk]]
                else:
                    for lk in list_keys:
                        unit[lk].append(entry[lk])
                LastEffectNo = NewEffectNo
            except Exception as e:
                logger.debug(f"{logger_prefix}Error loading entry {entry}: {e}")
        result_dict[LastSkillIdLv] = unit

    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(result_dict, out, ensure_ascii=False, indent=2)


def convert_all_yaml_files():
    # RhythmGameSkills
    generic_yaml_to_json(
        filepath="Data\\RhythmGameSkills.yaml",
        output_path="Data\\RhythmGameSkills.json",
        id_key="Id",
        group_id_from="Id",
        fixed_keys=["RhythmGameSkillSeriesId", "RhythmGameSkillName", "ConsumeAP", "Description"],
        list_keys=["RhythmGameSkillConditionIds", "RhythmGameSkillEffectId"],
        logger_prefix="RhythmGameSkills: "
    )

    # CenterSkills
    generic_yaml_to_json(
        filepath="Data\\CenterSkills.yaml",
        output_path="Data\\CenterSkills.json",
        id_key="Id",
        group_id_from="Id",
        fixed_keys=["CenterSkillSeriesId", "CenterSkillName", "Description"],
        list_keys=["CenterSkillConditionIds", "CenterSkillEffectId"],
        logger_prefix="CenterSkills: "
    )

    # CenterAttributes
    generic_yaml_to_json(
        filepath="Data\\CenterAttributes.yaml",
        output_path="Data\\CenterAttributes.json",
        id_key="Id",
        group_id_from="Id",
        fixed_keys=["CenterAttributeSeriesId", "CenterAttributeName", "Description"],
        list_keys=["TargetIds", "CenterAttributeEffectId"],
        logger_prefix="CenterAttributes: "
    )

    # CardDatas
    generic_yaml_to_json(
        filepath="Data\\CardDatas.yaml",
        output_path="Data\\CardDatas.json",
        id_key="Id",
        group_id_from="CardSeriesId",
        fixed_keys=["CardSeriesId", "Name", "Description", "CharactersId", "Rarity", "CenterSkillSeriesId", "CenterAttributeSeriesId"],
        list_keys=["MaxSmile", "MaxPure", "MaxCool", "MaxMental", "RhythmGameSkillSeriesId"],
        logger_prefix="CardDatas: "
    )


def db_load(path):
    with open(path, 'r', encoding='UTF-8') as f:
        return json.load(f)


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(message)s'
    )
    convert_all_yaml_files()
