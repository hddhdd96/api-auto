import { randomUUID } from 'node:crypto';

const UNIQUE_SUFFIX_LENGTH = 8;
const DEFAULT_VOLUME_SIZE_GIB = 1;

export type VolumeTestData = {
  name: string;
  sizeGiB: number;
};

export function createVolumeTestData(): VolumeTestData {
  const uniqueSuffix = randomUUID().slice(0, UNIQUE_SUFFIX_LENGTH);

  return {
    name: `portfolio-volume-${uniqueSuffix}`,
    sizeGiB: DEFAULT_VOLUME_SIZE_GIB,
  };
}
