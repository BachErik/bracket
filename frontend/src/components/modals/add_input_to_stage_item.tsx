import { Button, Modal } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useTranslation } from 'next-i18next';
import React from 'react';
import { SWRResponse } from 'swr';

import { StageItemWithRounds } from '../../interfaces/stage_item';
import { Tournament } from '../../interfaces/tournament';
import { getStageItemLookup, getTeamsLookup } from '../../services/lookups';
import { getAvailableInputs, updateStageItem } from '../../services/stage_item';
import { StageItemInput } from './create_stage_item';

export function AddInputToStageItemModal({
  tournament,
  opened,
  setOpened,
  stageItem,
  swrStagesResponse,
}: {
  tournament: Tournament;
  opened: boolean;
  setOpened: any;
  stageItem: StageItemWithRounds;
  swrStagesResponse: SWRResponse;
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: { name: stageItem.name },
    validate: {},
  });

  // TODO: Refactor lookups into one request.
  const teamsMap = getTeamsLookup(tournament != null ? tournament.id : -1);
  const stageItemMap = getStageItemLookup(swrStagesResponse);

  return (
    <Modal opened={opened} onClose={() => setOpened(false)} title="Add team to stage item">
      <form
        onSubmit={form.onSubmit(async (values) => {
          await updateStageItem(tournament.id, stageItem.id, values.name);
          await swrStagesResponse.mutate();
          setOpened(false);
        })}
      >
        {teamsMap != null && stageItemMap != null ? (
          <StageItemInput
            possibleOptions={getAvailableInputs(
              tournament,
              stageItem.stage_id,
              teamsMap,
              stageItemMap
            )}
            form={form}
            index={null}
          />
        ) : null}
        <Button fullWidth style={{ marginTop: 16 }} color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
    </Modal>
  );
}
