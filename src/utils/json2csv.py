import json
import csv
import os
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def convert_single_song_results_to_csv(json_filepath: str, csv_filepath: str):
    """
    Converts a JSON file containing single-song simulation results to a CSV file.
    Expected JSON format: [{"deck_card_ids": [...], "score": ...}, ...]
    """
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            logger.error(f"Error: JSON data in '{json_filepath}' is not in the expected list of dictionaries format for single song results.")
            return

        if not data:
            logger.info(f"No data found in '{json_filepath}'. Skipping CSV conversion.")
            return

        # Determine CSV headers
        # We expect 'deck_card_ids' and 'score'. Card IDs will be expanded to Card1, Card2, ... Card6
        headers = ['Score'] + [f'Card{i+1}' for i in range(6)]  # Assuming 6 cards per deck

        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)  # Write header row

            for row_data in data:
                score = row_data.get('score', 'N/A')
                card_ids = row_data.get('deck_card_ids', [])

                # Ensure card_ids list has exactly 6 elements, pad with None or empty string if less
                # Or truncate if more (though decks are typically fixed at 6)
                csv_row = [score] + (card_ids + [''] * 6)[:6]
                writer.writerow(csv_row)

        logger.info(f"Successfully converted '{json_filepath}' to '{csv_filepath}' (Single Song Results).")

    except FileNotFoundError:
        logger.error(f"Error: JSON file not found at '{json_filepath}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from '{json_filepath}': {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during conversion: {e}")


def convert_multi_song_combo_to_csv(json_filepath: str, csv_filepath: str):
    """
    Converts a JSON file containing the best 3-song combo results to a CSV file.
    Expected JSON format: {"total_score": ..., "decks": [{"music_id": ..., "difficulty": ..., "deck_card_ids": [...], "score": ...}, ...]}
    """
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict) or "total_score" not in data or "decks" not in data:
            logger.error(f"Error: JSON data in '{json_filepath}' is not in the expected format for multi-song combo results.")
            return

        total_score = data.get('total_score', 'N/A')
        decks = data.get('decks', [])

        if not decks:
            logger.info(f"No deck data found in '{json_filepath}'. Skipping CSV conversion.")
            return

        # Determine CSV headers
        # For multi-song combo, it's more about the specific song, its score, and the 6 cards
        headers = ['Total_Score', 'Song_Index', 'Music_ID', 'Difficulty', 'Song_Score'] + [f'Card{i+1}' for i in range(6)]

        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)  # Write header row

            # Write total score as the first element in the first row, then empty for subsequent rows
            first_row_written = False
            for i, deck_info in enumerate(decks):
                music_id = deck_info.get('music_id', 'N/A')
                difficulty = deck_info.get('difficulty', 'N/A')
                song_score = deck_info.get('score', 'N/A')
                card_ids = deck_info.get('deck_card_ids', [])

                row_total_score = total_score if not first_row_written else ''  # Only write total score once
                first_row_written = True

                csv_row = [row_total_score, i + 1, music_id, difficulty, song_score] + (card_ids + [''] * 6)[:6]
                writer.writerow(csv_row)

        logger.info(f"Successfully converted '{json_filepath}' to '{csv_filepath}' (Multi-Song Combo Results).")

    except FileNotFoundError:
        logger.error(f"Error: JSON file not found at '{json_filepath}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from '{json_filepath}': {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during conversion: {e}")


def main():
    parser = argparse.ArgumentParser(description="Convert JSON simulation results to CSV format.")
    parser.add_argument("json_file", type=str, help="Path to the input JSON file.")
    parser.add_argument("-o", "--output", type=str,
                        help="Path for the output CSV file. Defaults to JSON filename with .csv extension.")
    parser.add_argument("-t", "--type", type=str, choices=['single', 'multi', 'auto'], default='auto',
                        help="Type of JSON file: 'single' for single song results, 'multi' for multi-song combo results, or 'auto' to detect (default).")

    args = parser.parse_args()

    json_filepath = args.json_file
    csv_filepath = args.output

    if not csv_filepath:
        base_name = os.path.splitext(os.path.basename(json_filepath))[0]
        csv_filepath = f"{base_name}.csv"

    if args.type == 'auto':
        # Try to automatically detect file type by attempting to load and check structure
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and all(isinstance(item, dict) and 'deck_card_ids' in item and 'score' in item for item in data):
                detected_type = 'single'
            elif isinstance(data, dict) and 'total_score' in data and 'decks' in data:
                detected_type = 'multi'
            else:
                logger.error(f"Could not automatically detect type for '{json_filepath}'. Please specify with -t argument ('single' or 'multi').")
                return
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading JSON file for type detection: {e}")
            return
    else:
        detected_type = args.type

    if detected_type == 'single':
        convert_single_song_results_to_csv(json_filepath, csv_filepath)
    elif detected_type == 'multi':
        convert_multi_song_combo_to_csv(json_filepath, csv_filepath)
    else:
        logger.error(f"Unsupported conversion type: {detected_type}. This should not happen if 'auto' detection or choices are correct.")


if __name__ == "__main__":
    convert_single_song_results_to_csv(r"log\simulation_results_305106_02.json", r"log\simulation_results_305106_02.csv")
    # main()
